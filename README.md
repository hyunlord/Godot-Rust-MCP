[![Tests](https://github.com/hyunlord/Godot-Rust-MCP/actions/workflows/test.yml/badge.svg)](https://github.com/hyunlord/Godot-Rust-MCP/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Godot 4.x](https://img.shields.io/badge/Godot-4.x-blue.svg)](https://godotengine.org/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)

# godot-rust-harness

**Your AI coding assistant can't press F5.** It can run `cargo build` and `cargo test`, but it can't launch your Godot game, advance 100 simulation ticks, and check whether entity health values went negative.

This plugin gives AI tools like [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Codex](https://openai.com/index/codex/) the ability to:

- 🚀 **Launch Godot headless** and connect to it programmatically
- ⏩ **Advance simulation ticks** and read entity state
- ✅ **Run runtime checks** (are values in bounds? any crashes?)
- 📊 **Benchmark performance** (did this change make ticks slower?)
- 🔄 **Full pipeline in one call** — build → lint → test → launch → check → stop

> **One command. Zero manual testing.**
>
> ```
> verify(package="my_crate", seed=42, agents=50, ticks=100)
> → { "passed": true, "failed_at": null }
> ```

---

## How It Works

```
Your AI assistant (Claude Code, Codex, etc.)
    │
    │  calls tools like: rust_build, godot_tick, godot_invariant
    │
    ▼
Python server (src/server.py)
    │
    ├─ cargo build / test / clippy    ← runs locally
    │
    └─ WebSocket → Godot (headless)   ← launches automatically
                   │
                   ├─ advance ticks
                   ├─ read entity data
                   ├─ run runtime checks
                   └─ measure performance
```

The Godot side is a lightweight addon (`addons/harness/`) that **only activates in headless mode**. Normal gameplay is completely unaffected.

---

## Quick Start

### Option A: Claude Code Plugin (Recommended)

**Step 1: Add the marketplace**

```
/plugin marketplace add https://github.com/hyunlord/Godot-Rust-MCP
```

**Step 2: Install the plugin**

```
/plugin install godot-rust-harness
```

That's it. When your AI assistant first calls `godot_start`, the Godot addon is
automatically installed in your project and the Autoload is registered. No manual
setup required.

### Option B: Manual Setup

<details>
<summary>Click to expand manual installation steps</summary>

#### 1. Clone and install dependencies

```bash
git clone https://github.com/hyunlord/Godot-Rust-MCP.git
cd Godot-Rust-MCP
pip install -r requirements.txt
```

#### 2. Copy the addon to your Godot project

```bash
cp -r addons/harness/ /path/to/your/godot-project/addons/
```

#### 3. Register the Autoload

In your Godot project: **Project → Project Settings → Autoload**

Add `res://addons/harness/harness_server.gd` as **HarnessServer** and enable it.

#### 4. Register the MCP server

Add this to your project's `.mcp.json` (create the file if it doesn't exist):

```json
{
  "mcpServers": {
    "godot-rust-harness": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/Godot-Rust-MCP",
      "env": {
        "PROJECT_ROOT": "/path/to/your/godot-rust-project",
        "GODOT_BIN": "godot"
      }
    }
  }
}
```

</details>

Your AI assistant now has 16 new tools for runtime verification.

---

## Available Tools (30)

### Build & Verify (16 tools)

| Tool | What it does |
|------|-------------|
| `rust_build` | Run `cargo build` (optional: specific crate, release mode) |
| `rust_test` | Run `cargo test` (optional: filter by test name) |
| `rust_clippy` | Run `cargo clippy -- -D warnings` |
| `godot_start` | Launch Godot in headless mode, connect via WebSocket |
| `godot_stop` | Shut down Godot and close connection |
| `godot_reset` | Reset simulation with a specific RNG seed and agent count |
| `godot_tick` | Advance the simulation by N ticks |
| `godot_snapshot` | Get a summary of all alive entities (capped at 200) |
| `godot_query` | Get full details of one entity or settlement by ID |
| `godot_scene_tree` | Get the Godot scene tree as JSON |
| `godot_bench` | Benchmark tick performance (avg, min, max, p95, median) |
| `godot_invariant` | Run runtime checks on entity data |
| `godot_force_event` | Inject an event on a specific entity |
| `godot_set_config` | Change a simulation config value at runtime |
| `godot_golden_dump` | Save full simulation state to a JSON file |
| `verify` | Build → clippy → test → start → reset → tick → check → stop |

### Code Analysis (3 tools)

| Tool | What it does |
|------|-------------|
| `rust_analyze` | Find code quality issues: `.unwrap()`, `unsafe` blocks, clone-heavy patterns, clippy warnings |
| `rust_dependencies` | Analyze crate dependency tree; show outdated deps (requires `cargo-outdated`) |
| `crate_map` | Visualize workspace crate dependency graph (text or Mermaid format) |

### Project Structure (1 tool)

| Tool | What it does |
|------|-------------|
| `project_overview` | Full project scan: Rust crates, Godot autoloads/scenes, gdext bridge classes (`#[func]`, `#[signal]`) |

### Debug & Diagnose (2 tools)

| Tool | What it does |
|------|-------------|
| `diagnose` | Analyze a build/runtime error and suggest fixes from a known pattern DB |
| `build_explain` | Run `cargo build` and return errors with plain-language explanations |

### gdext Patterns (3 tools)

| Tool | What it does |
|------|-------------|
| `gdext_check` | Validate gdext usage patterns — 15 rules across safety, performance, and patterns |
| `gdext_scaffold` | Generate boilerplate for: godot_class, singleton, resource, bridge_class, signal_hub, export_enum |
| `gdext_version_check` | Check gdext Cargo.toml version vs Godot binary for compatibility warnings |

### GDScript → Rust Migration (3 tools)

| Tool | What it does |
|------|-------------|
| `migration_scan` | Analyze GDScript files: classify, estimate effort, generate Rust skeleton (detail mode) |
| `migration_diff` | Compare original GDScript with converted Rust — method coverage and pattern mapping |
| `migration_validate` | Compare two golden dumps (before/after) for numerical parity within tolerance |

### Performance (2 tools)

| Tool | What it does |
|------|-------------|
| `perf_suggest` | Scan Rust code for optimization opportunities — 12 rules across memory, cpu, ffi, ecs |
| `rust_unsafe_audit` | Audit all unsafe blocks, FFI boundaries, and raw pointers; flags missing SAFETY comments |

---

## Runtime Checks (Invariants)

The plugin ships with 7 built-in checks that validate entity data after ticking:

| Check | What it catches |
|-------|----------------|
| `needs_bounded` | Need values outside [0.0, 1.0] |
| `emotions_bounded` | Emotion values outside [0.0, 1.0] |
| `personality_bounded` | Personality axis values outside [0.0, 1.0] |
| `health_bounded` | Health outside [0.0, 1.0] |
| `age_non_negative` | Negative age values |
| `stress_non_negative` | Negative stress values |
| `no_duplicate_traits` | Same trait appearing twice on one entity |

These checks work on Dictionary fields returned by your adapter's `serialize_entity_full()` method. You can add your own:

```gdscript
# In harness_invariants.gd or your adapter setup:
_register("my_custom_check", func(entities: Array) -> Array:
    var violations: Array = []
    for e in entities:
        if e.get("mana", 0.0) > 100.0:
            violations.append({"entity_id": e.id, "field": "mana", "value": e.mana})
    return violations
)
```

---

## Connecting to Your Project (Adapters)

Out of the box, the harness tries to find your simulation engine at common node paths (`/root/SimulationEngine`, `/root/GameManager`, etc.) and call common tick methods (`step()`, `process_single_tick()`, etc.).

If your project uses different names or patterns, create an **adapter** — a single file that tells the harness how to talk to your code:

### 1. Copy the template

```bash
cp Godot-Rust-MCP/examples/example_adapter.gd \
   your-project/addons/harness/myproject_adapter.gd
```

### 2. Fill in the blanks

```gdscript
extends Node

func get_engine():
    return get_node_or_null("/root/Main").sim_engine

func process_ticks(n: int) -> void:
    get_engine().advance_ticks(n)

func get_current_tick() -> int:
    return get_engine().current_tick

func get_alive_entities() -> Array:
    return get_node_or_null("/root/Main").entity_manager.get_alive_entities()

func get_alive_count() -> int:
    return get_alive_entities().size()

func get_entity(id: int):
    return get_node_or_null("/root/Main").entity_manager.get_entity(id)

func reset_simulation(seed: int, agents: int) -> void:
    get_engine().init_with_seed(seed)

func serialize_entity_summary(e) -> Dictionary:
    return {"id": e.id, "is_alive": e.is_alive, "name": e.name, "health": e.health}

func serialize_entity_full(e) -> Dictionary:
    var d = serialize_entity_summary(e)
    d["needs"] = {"hunger": e.hunger, "energy": e.energy}
    d["emotions"] = e.emotions.duplicate()
    return d
```

### 3. Restart Godot headless

The harness auto-discovers any `*_adapter.gd` file in `addons/harness/`. No configuration needed.

See `examples/example_adapter.gd` for a fully-commented template with all available methods.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ROOT` | `.` | Root of your Godot+Rust project |
| `GODOT_BIN` | `godot` | Path to Godot 4.x binary |

---

## Zero Impact on Your Game

The harness addon **only activates** when Godot runs with `--headless` or `--harness` flags. During normal gameplay (F5, exported builds), it does absolutely nothing — no overhead, no side effects.

---

## Running the Plugin's Own Tests

```bash
cd Godot-Rust-MCP
pip install -r requirements.txt
python -m pytest tests/ -v    # 54 tests
```

## Smoke Test (against your Godot project)

```bash
godot --path /path/to/your/project --headless &
sleep 5
python Godot-Rust-MCP/examples/smoke_test.py
kill %1
```

---

## License

MIT — see [LICENSE](LICENSE).
