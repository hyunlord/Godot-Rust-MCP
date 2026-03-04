# godot-rust-harness

MCP plugin that gives AI coding agents (Claude Code, Codex) the ability to launch Godot headless, advance simulation ticks, query entity state, run invariant checks, and benchmark performance — all from within the tool-calling interface.

## Why

After writing Godot+Rust simulation code, agents can run `cargo build` and `cargo test` but cannot verify runtime behavior. This plugin eliminates that gap:

- Does the simulation crash at runtime?
- Are entity values staying within valid bounds after 100 ticks?
- Did a code change cause a performance regression?
- Is the scene tree correctly structured?

## Architecture

```
Claude Code (MCP client)
    ↓ tool calls
src/server.py (MCP server, Python)
    ↓ JSON-RPC 2.0 over WebSocket
addons/harness/harness_server.gd (Godot autoload)
    ↓
addons/harness/harness_router.gd (command dispatcher)
addons/harness/harness_invariants.gd (invariant checks)
```

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Register MCP server with Claude Code

The `.mcp.json` file in this repo registers the server. Set `PROJECT_ROOT` to your Godot+Rust project root:

```json
{
  "mcpServers": {
    "godot-rust-harness": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

### 3. Install the Godot addon

Copy `addons/harness/` into your Godot project:

```bash
cp -r addons/harness/ /path/to/your/godot-project/addons/
```

### 4. Register as Autoload

In your Godot project: **Project → Project Settings → Autoload**

- Add `res://addons/harness/harness_server.gd` as `HarnessServer`
- Enable it

### 5. Set GODOT_BIN (if not in PATH)

```bash
export GODOT_BIN=/path/to/godot4
```

## Available MCP Tools

### Rust tools

| Tool | Description |
|------|-------------|
| `rust_build` | `cargo build [-p PKG] [--release]` |
| `rust_test` | `cargo test [-p PKG] [-- FILTER]` |
| `rust_clippy` | `cargo clippy -- -D warnings` |

### Godot lifecycle tools

| Tool | Description |
|------|-------------|
| `godot_start` | Launch Godot headless, connect WebSocket |
| `godot_stop` | Kill Godot process, close WebSocket |

### Simulation tools

| Tool | Params | Description |
|------|--------|-------------|
| `godot_tick` | `n=1` | Advance N simulation ticks |
| `godot_snapshot` | — | Get entity count and first 200 alive entities |
| `godot_query` | `type, id` | Get full detail of one entity or settlement |
| `godot_scene_tree` | `depth=3` | Get Godot scene tree as JSON |
| `godot_invariant` | `name=""` | Run invariant checks (all or one) |
| `godot_reset` | `seed=42, agents=50` | Reset simulation deterministically |
| `godot_bench` | `n=100, warmup=10` | Benchmark tick performance |

### Composite tool

| Tool | Description |
|------|-------------|
| `verify` | Build → test → start → reset → tick → invariant → stop |

## Invariants

Seven built-in invariants (all run by default with `name=""`):

| Name | Checks |
|------|--------|
| `needs_bounded` | All need values ∈ [0.0, 1.0] |
| `emotions_bounded` | Plutchik 8 emotions ∈ [0.0, 1.0] |
| `personality_bounded` | HEXACO axes ∈ [0.0, 1.0] |
| `health_bounded` | health ∈ [0.0, 1.0] |
| `age_non_negative` | age ≥ 0 |
| `stress_non_negative` | stress_level ≥ 0 |
| `no_duplicate_traits` | No trait_id appears twice per entity |

Add custom invariants by calling `_register(name, callable)` in `harness_invariants.gd`.

## Usage Example

```python
# In Claude Code, the agent calls these tools:

# 1. Start Godot
godot_start(port=9877)

# 2. Reset with deterministic seed
godot_reset(seed=42, agents=50)

# 3. Run 100 ticks
godot_tick(n=100)

# 4. Check invariants
godot_invariant(name="")
# → {"total": 7, "passed": 7, "failed": 0, "results": [...]}

# 5. Run full verification pipeline in one call
verify(package="my_crate", seed=42, agents=50, ticks=100)
# → {"passed": true, "failed_at": null, "steps": {...}}
```

## Integration with SimulationEngine

The harness looks for your simulation engine at these node paths (in order):

- `/root/SimulationEngine`
- `/root/SimEngine`
- `/root/Simulation`
- `/root/GameManager`
- `/root/World`

The engine node must implement one of these tick methods:

- `process_single_tick()`
- `_process_tick()`
- `step()`

Entity data is accessed via `/root/EntityManager`. The manager must implement `get_all_entities() -> Array`.

## Running Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

## Smoke Test (requires live Godot)

```bash
godot --path /path/to/project --headless &
sleep 5
python examples/smoke_test.py
kill %1
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ROOT` | `.` | Root of the Rust/Godot project |
| `GODOT_BIN` | `godot` | Path to Godot 4.x binary |

## How It Works (Godot side)

`harness_server.gd` activates only when:
- Godot is launched with `--headless`, OR
- The `--harness` command-line flag is present

In normal gameplay (F5), the harness does nothing — zero performance impact.

The server uses Godot's built-in `TCPServer` + `WebSocketPeer` to accept connections and process JSON-RPC 2.0 messages every frame in `_process()`.
