# AGENTS.md — godot-rust-harness

> Behavior rules for AI implementors (Codex, Claude Code) working on this repo.

---

## Your Role

You are implementing a developer tool — an MCP plugin + Godot addon.
You are NOT implementing game logic, simulation systems, or UI.

### What you build
- Python MCP server that wraps cargo CLI + Godot WebSocket
- GDScript addon that exposes Godot internals via WebSocket JSON-RPC
- Tests for both

### What you do NOT build
- Game mechanics, simulation systems, entity logic
- User-facing UI, menus, HUD
- Localization files, translation keys
- CI/CD pipelines (future scope)

---

## Implementation Rules

### Rule 1: One ticket = one file
Each dispatched ticket targets exactly ONE file. If you need to change 2 files,
that is 2 tickets. The only exception is DIRECT integration wiring (<50 lines across files).

### Rule 2: Type everything
- Python: `def send(self, method: str, params: dict) -> dict:`
- GDScript: `func execute(method: String, params: Dictionary) -> Dictionary:`
- No `Any`, no `Variant` unless absolutely necessary with documented reason.

### Rule 3: Error handling pattern
Every function that can fail returns a result dict, never raises/crashes.

**Python MCP tools:**
```python
async def call_tool(name: str, args: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, args)
        return [TextContent(type="text", text=json.dumps(result))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]
```

**GDScript commands:**
```gdscript
func execute(method: String, params: Dictionary) -> Dictionary:
    match method:
        "ping":
            return {"result": {"pong": true}}
        _:
            return {"error": {"code": -32601, "message": "Unknown: %s" % method}}
```

### Rule 4: Harness activation guard
The Godot addon MUST only activate when:
- `DisplayServer.get_name() == "headless"`, OR
- `"--harness"` is in `OS.get_cmdline_args()`

Normal gameplay MUST NOT be affected. Zero overhead when inactive.

### Rule 5: No hardcoded project paths
The harness discovers Godot nodes dynamically:
```gdscript
var engine = get_node_or_null("/root/SimulationEngine")
if engine == null:
    return {"error": {"code": -32000, "message": "SimulationEngine not found"}}
```

Node names (`SimulationEngine`, `EntityManager`) are conventions, not hardcoded dependencies.
If a target project uses different names, the harness returns clear error messages.

### Rule 6: WebSocket protocol is JSON-RPC 2.0
Every request:
```json
{"jsonrpc": "2.0", "id": 1, "method": "tick", "params": {"n": 100}}
```
Every success response:
```json
{"jsonrpc": "2.0", "id": 1, "result": {"ticks_run": 100}}
```
Every error response:
```json
{"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "Unknown method"}}
```

Standard error codes:
| Code | Meaning |
|------|---------|
| -32700 | Parse error (invalid JSON) |
| -32600 | Invalid request (missing method/id) |
| -32601 | Method not found |
| -32602 | Invalid params |
| -32000 | Server error (node not found, etc.) |

### Rule 7: Log prefix
All GDScript log messages: `[Harness] message here`
All Python log messages: `[MCP] message here`

### Rule 8: Invariant pattern
Every invariant function follows this exact pattern:
```gdscript
func _check_FIELDNAME_CONDITION() -> Array:
    var violations: Array = []
    for entity in _get_alive():
        if VIOLATION_CONDITION:
            violations.append({
                "entity": entity.id,
                "field": "FIELD_NAME",
                "value": ACTUAL_VALUE,
                "expected": "CONDITION_DESCRIPTION"
            })
    return violations  # empty = PASS
```

Register in `_ready()`:
```gdscript
_register("FIELDNAME_CONDITION", _check_FIELDNAME_CONDITION)
```

---

## File-by-File Specifications

### src/server.py
- Entry point: `async def main()` → `stdio_server()` → `app.run()`
- Defines ALL MCP tools via `@app.list_tools()` and `@app.call_tool()`
- Tool categories: `rust_*` (subprocess), `godot_*` (WebSocket proxy), `verify` (composite)
- Global state: `godot: GodotWS | None`, `godot_proc: subprocess.Popen | None`
- Subprocess timeout: 300s for cargo, 15s for Godot startup
- Output truncation: stdout/stderr capped at 3000 chars

### src/godot_ws.py
- Class `GodotWS` with async methods
- `connect_with_retry(timeout: float) -> bool` — retry every 0.3s
- `send(method: str, params: dict) -> dict` — JSON-RPC request, 300s recv timeout
- `close() -> None` — graceful WebSocket close
- Auto-incrementing request ID

### addons/harness/harness_server.gd
- Autoload Node
- `TCPServer` on port 9877 (const `PORT`)
- `_process()`: accept connections, poll peers, read/write packets
- `_should_start() -> bool`: headless or --harness check
- Peer cleanup on STATE_CLOSED
- Tree exit cleanup

### addons/harness/harness_router.gd
- `HarnessRouter` class (extends Node)
- `execute(method: String, params: Dictionary) -> Dictionary`
- 11 methods: ping, tick, snapshot, query, scene_tree, invariant, reset, bench, force_event, set_config, golden_dump
- Each method is a private `_cmd_METHOD(params)` function
- Helper functions: `_engine()`, `_entity_manager()`, `_tick()`, `_alive_count()`, `_serialize_entity_full()`

### addons/harness/harness_invariants.gd
- `HarnessInvariants` class (extends Node)
- Registry: `_checks: Dictionary` mapping name → Callable
- `run_all() -> Dictionary`: returns `{total, passed, failed, results[]}`
- `run_single(name: String) -> Dictionary`: returns `{name, passed, violations[]}`
- Violations capped at 20 per invariant (prevent OOM on massive failures)
- Ships with 7 default invariants (extensible by target project)

### addons/harness/plugin.cfg
```ini
[plugin]
name="Godot Rust Harness"
description="WebSocket server for AI-assisted runtime verification"
author="WorldSim"
version="0.1.0"
script="harness_server.gd"
```

---

## Verification Checklist

Before completing ANY ticket, confirm:

- [ ] File compiles (`py_compile` for Python, Godot scene load for GDScript)
- [ ] All functions have type hints / static typing
- [ ] Error cases return dict with "error" key, never crash
- [ ] No hardcoded project-specific paths
- [ ] Log messages use correct prefix (`[Harness]` or `[MCP]`)
- [ ] If GDScript: activation guard present (headless/--harness only)
- [ ] If invariant: follows the standard pattern with violations array
- [ ] PROGRESS.md updated with result