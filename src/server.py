import asyncio
import json
import os
import subprocess
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .godot_ws import GodotWS

app = Server("godot-rust-harness")
ROOT = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()

_godot: GodotWS | None = None
_godot_proc: subprocess.Popen | None = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _cargo(cmd: str, package: str = "", extra: list[str] | None = None) -> dict:
    args = ["cargo", cmd]
    if package:
        args += ["-p", package]
    if extra:
        args += extra
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=str(ROOT), timeout=300
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:],
            "stderr": result.stderr[-3000:],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "returncode": -1, "stdout": "", "stderr": "Timeout after 300s"}
    except FileNotFoundError:
        return {"success": False, "returncode": -1, "stdout": "", "stderr": "cargo not found in PATH"}


async def _godot_start(port: int = 9877) -> dict:
    global _godot, _godot_proc

    if _godot is not None and _godot.connected:
        return {"status": "already_running", "port": port}

    # Kill stale process if any
    await _godot_stop()

    godot_bin = os.environ.get("GODOT_BIN", "godot")

    # Find project path
    godot_subdir = ROOT / "godot"
    if (godot_subdir / "project.godot").exists():
        project_path = str(godot_subdir)
    elif (ROOT / "project.godot").exists():
        project_path = str(ROOT)
    else:
        return {"error": f"No project.godot found in {godot_subdir} or {ROOT}. Set PROJECT_ROOT env var."}

    try:
        _godot_proc = subprocess.Popen(
            [godot_bin, "--path", project_path, "--headless"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return {"error": f"Godot binary not found: {godot_bin!r}. Set GODOT_BIN env var."}

    _godot = GodotWS(port)
    connected = await _godot.connect_with_retry(timeout=15.0)
    if not connected:
        _godot_proc.kill()
        _godot_proc = None
        _godot = None
        return {"error": "Failed to connect to Godot harness after 15s. Is harness_server.gd registered as an Autoload?"}

    # Verify with ping
    try:
        ping = await _godot.send("ping", {})
    except Exception as exc:
        await _godot_stop()
        return {"error": f"Connected but ping failed: {exc}"}

    return {
        "status": "connected",
        "pid": _godot_proc.pid,
        "port": port,
        "ping": ping,
    }


async def _godot_stop() -> dict:
    global _godot, _godot_proc
    msgs: list[str] = []

    if _godot is not None:
        await _godot.close()
        _godot = None
        msgs.append("WebSocket closed")

    if _godot_proc is not None:
        _godot_proc.terminate()
        try:
            _godot_proc.wait(timeout=5)
            msgs.append("Process terminated")
        except subprocess.TimeoutExpired:
            _godot_proc.kill()
            msgs.append("Process killed (timeout)")
        _godot_proc = None

    if not msgs:
        return {"status": "not_running"}
    return {"status": "stopped", "actions": msgs}


def _godot_check() -> dict | None:
    if _godot is None or not _godot.connected:
        return {"error": "Godot not running. Call godot_start first."}
    return None


async def _verify(args: dict) -> dict:
    steps: dict = {}
    pkg = args.get("package", "")

    # Step 1: cargo build
    steps["build"] = _cargo("build", pkg)
    if not steps["build"]["success"]:
        return {"passed": False, "failed_at": "build", "steps": steps}

    # Step 2: cargo test
    steps["test"] = _cargo("test", pkg)
    if not steps["test"]["success"]:
        return {"passed": False, "failed_at": "test", "steps": steps}

    # Step 3: Godot start
    steps["start"] = await _godot_start(9877)
    if "error" in steps["start"]:
        return {"passed": False, "failed_at": "godot_start", "steps": steps}

    try:
        # Step 4: Reset
        steps["reset"] = await _godot.send("reset", {
            "seed": args.get("seed", 42),
            "agents": args.get("agents", 50),
        })

        # Step 5: Tick
        steps["tick"] = await _godot.send("tick", {"n": args.get("ticks", 100)})

        # Step 6: Invariant
        steps["invariant"] = await _godot.send("invariant", {"name": ""})
        inv_passed = steps["invariant"].get("failed", 1) == 0

        return {
            "passed": inv_passed,
            "failed_at": None if inv_passed else "invariant",
            "steps": steps,
        }
    finally:
        await _godot_stop()


# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="rust_build",
        description="Run `cargo build` in PROJECT_ROOT. Returns success, returncode, stdout, stderr.",
        inputSchema={
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Crate name to build (-p PKG)"},
                "release": {"type": "boolean", "description": "Build in release mode (--release)"},
            },
        },
    ),
    Tool(
        name="rust_test",
        description="Run `cargo test` in PROJECT_ROOT. Returns success, returncode, stdout, stderr.",
        inputSchema={
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Crate name (-p PKG)"},
                "filter": {"type": "string", "description": "Test name filter string"},
            },
        },
    ),
    Tool(
        name="rust_clippy",
        description="Run `cargo clippy -- -D warnings`. Returns success, returncode, stdout, stderr.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="godot_start",
        description=(
            "Launch Godot in headless mode and connect to the harness WebSocket server. "
            "Uses GODOT_BIN env var for binary path. Looks for project.godot in PROJECT_ROOT/godot/ or PROJECT_ROOT/."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "port": {"type": "integer", "description": "WebSocket port (default 9877)", "default": 9877},
            },
        },
    ),
    Tool(
        name="godot_stop",
        description="Terminate the Godot process and close the WebSocket connection.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="godot_tick",
        description="Advance the simulation by N ticks (clamped to [1, 100000]). Godot must be running.",
        inputSchema={
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Number of ticks to advance (default 1)"},
            },
        },
    ),
    Tool(
        name="godot_snapshot",
        description=(
            "Get simulation state summary: tick count, total/alive entity counts, "
            "first 200 alive entities (truncated if more)."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="godot_query",
        description="Get full detail of a single entity or settlement by ID.",
        inputSchema={
            "type": "object",
            "required": ["type", "id"],
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["entity", "settlement"],
                    "description": "Whether to query an entity or settlement",
                },
                "id": {"type": "integer", "description": "ID of the entity or settlement"},
            },
        },
    ),
    Tool(
        name="godot_scene_tree",
        description="Get the Godot scene tree as a recursive JSON structure.",
        inputSchema={
            "type": "object",
            "properties": {
                "depth": {"type": "integer", "description": "Max recursion depth (default 3)"},
            },
        },
    ),
    Tool(
        name="godot_invariant",
        description=(
            "Run simulation invariant checks. name='' runs all 7 default invariants. "
            "Returns {total, passed, failed, results[{name, passed, violations[]}]}."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Invariant name or '' for all. Options: needs_bounded, emotions_bounded, "
                                   "personality_bounded, health_bounded, age_non_negative, stress_non_negative, "
                                   "no_duplicate_traits",
                },
            },
        },
    ),
    Tool(
        name="godot_reset",
        description="Reset the simulation with a deterministic RNG seed and initial agent count.",
        inputSchema={
            "type": "object",
            "properties": {
                "seed": {"type": "integer", "description": "RNG seed (default 42)"},
                "agents": {"type": "integer", "description": "Initial agent count (default 50)"},
            },
        },
    ),
    Tool(
        name="godot_bench",
        description=(
            "Benchmark tick performance. Runs warmup ticks (unmeasured), then measures N ticks individually. "
            "Returns avg_ms, min_ms, max_ms, p95_ms, median_ms."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Ticks to measure (default 100)"},
                "warmup": {"type": "integer", "description": "Warmup ticks before measurement (default 10)"},
            },
        },
    ),
    Tool(
        name="verify",
        description=(
            "Run the full verification pipeline: cargo build → cargo test → "
            "godot start → reset → tick → invariant check → godot stop. "
            "Returns {passed: bool, failed_at: str|null, steps: dict}."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Crate name for build/test steps"},
                "seed": {"type": "integer", "description": "Reset seed (default 42)"},
                "agents": {"type": "integer", "description": "Initial agents (default 50)"},
                "ticks": {"type": "integer", "description": "Ticks to advance (default 100)"},
            },
        },
    ),
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    args = arguments or {}
    result = await _dispatch(name, args)
    return [TextContent(type="text", text=json.dumps(result, indent=2))]


async def _dispatch(name: str, args: dict) -> dict:
    match name:
        case "rust_build":
            extra = ["--release"] if args.get("release") else None
            return _cargo("build", args.get("package", ""), extra)

        case "rust_test":
            extra: list[str] = []
            if args.get("filter"):
                extra = ["--", args["filter"]]
            return _cargo("test", args.get("package", ""), extra or None)

        case "rust_clippy":
            return _cargo("clippy", "", ["--", "-D", "warnings"])

        case "godot_start":
            return await _godot_start(args.get("port", 9877))

        case "godot_stop":
            return await _godot_stop()

        case "godot_tick":
            if err := _godot_check():
                return err
            n = max(1, min(int(args.get("n", 1)), 100000))
            return await _godot.send("tick", {"n": n})

        case "godot_snapshot":
            if err := _godot_check():
                return err
            return await _godot.send("snapshot", {})

        case "godot_query":
            if err := _godot_check():
                return err
            return await _godot.send("query", {
                "type": args.get("type", "entity"),
                "id": int(args.get("id", 0)),
            })

        case "godot_scene_tree":
            if err := _godot_check():
                return err
            return await _godot.send("scene_tree", {"depth": int(args.get("depth", 3))})

        case "godot_invariant":
            if err := _godot_check():
                return err
            return await _godot.send("invariant", {"name": args.get("name", "")})

        case "godot_reset":
            if err := _godot_check():
                return err
            return await _godot.send("reset", {
                "seed": int(args.get("seed", 42)),
                "agents": int(args.get("agents", 50)),
            })

        case "godot_bench":
            if err := _godot_check():
                return err
            return await _godot.send("bench", {
                "n": int(args.get("n", 100)),
                "warmup": int(args.get("warmup", 10)),
            })

        case "verify":
            return await _verify(args)

        case _:
            return {"error": f"Unknown tool: {name!r}"}


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
