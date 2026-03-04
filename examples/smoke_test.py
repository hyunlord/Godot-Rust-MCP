"""
Smoke test for godot-rust-harness.

Requires a live Godot instance with harness_server.gd registered as Autoload,
running in headless or --harness mode on port 9877.

Usage:
    godot --path /path/to/project --headless &
    sleep 5
    python examples/smoke_test.py
    kill %1

Expected output:
    PASS ping
    PASS scene_tree
    PASS tick
    PASS invariant
    PASS snapshot
    All smoke tests PASSED
"""
import asyncio
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.godot_ws import GodotWS

PORT = 9877
CONNECT_TIMEOUT = 15.0

RESULTS: list[tuple[str, bool, str]] = []


def report(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    msg = f"{status} {name}"
    if detail:
        msg += f": {detail}"
    print(msg)
    RESULTS.append((name, passed, detail))


async def run_smoke_tests() -> bool:
    gws = GodotWS(PORT)
    print(f"Connecting to ws://127.0.0.1:{PORT} (timeout={CONNECT_TIMEOUT}s)...")

    connected = await gws.connect_with_retry(timeout=CONNECT_TIMEOUT)
    if not connected:
        print(f"FAIL: Could not connect to Godot harness on port {PORT}")
        print("Is Godot running with harness_server.gd as Autoload in --headless mode?")
        return False

    print("Connected.")

    try:
        # Test: ping
        result = await gws.send("ping", {})
        if "error" in result:
            report("ping", False, str(result["error"]))
        elif "pong" not in result:
            report("ping", False, f"No 'pong' in response: {result}")
        else:
            report("ping", True, f"tick={result.get('tick', '?')}")

        # Test: scene_tree
        result = await gws.send("scene_tree", {"depth": 2})
        if "error" in result:
            report("scene_tree", False, str(result["error"]))
        elif "name" not in result and "type" not in result:
            report("scene_tree", False, f"Unexpected response: {result}")
        else:
            report("scene_tree", True, f"root={result.get('name', '?')}")

        # Test: tick
        result = await gws.send("tick", {"n": 1})
        if "error" in result:
            # Acceptable if SimulationEngine not present in test project
            err_msg = result["error"].get("message", str(result["error"]))
            if "SimulationEngine" in err_msg:
                report("tick", True, f"SKIP (no SimulationEngine): {err_msg}")
            else:
                report("tick", False, err_msg)
        elif "ticks_run" not in result:
            report("tick", False, f"No 'ticks_run' in response: {result}")
        else:
            report("tick", True, f"ticks_run={result['ticks_run']}, tick_now={result.get('tick_now', '?')}")

        # Test: invariant (all checks)
        result = await gws.send("invariant", {"name": ""})
        if "error" in result:
            report("invariant", False, str(result["error"]))
        elif "total" not in result:
            report("invariant", False, f"No 'total' in response: {result}")
        else:
            total = result["total"]
            passed_count = result.get("passed", 0)
            failed_count = result.get("failed", 0)
            report(
                "invariant",
                True,
                f"total={total}, passed={passed_count}, failed={failed_count}",
            )
            if failed_count > 0:
                print("  WARNING: Some invariants failed:")
                for r in result.get("results", []):
                    if not r.get("passed", True):
                        print(f"    FAIL {r['name']}: {r.get('violation_count', '?')} violations")

        # Test: snapshot
        result = await gws.send("snapshot", {})
        if "error" in result:
            report("snapshot", False, str(result["error"]))
        elif "tick" not in result:
            report("snapshot", False, f"No 'tick' in response: {result}")
        else:
            report(
                "snapshot",
                True,
                f"tick={result['tick']}, alive={result.get('alive', '?')}, "
                f"total={result.get('total_entities', '?')}",
            )

    finally:
        await gws.close()

    # Summary
    all_passed = all(p for _, p, _ in RESULTS)
    print()
    if all_passed:
        print("All smoke tests PASSED")
    else:
        failed = [n for n, p, _ in RESULTS if not p]
        print(f"FAILED tests: {', '.join(failed)}")

    return all_passed


def main() -> None:
    ok = asyncio.run(run_smoke_tests())
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
