---
description: "Set up the Godot addon in your project after installing the plugin"
argument-hint: "[path/to/your/godot-project]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
---

# Godot Rust Harness — Project Setup

The MCP server is already running (registered automatically when you installed the plugin).
Now let's install the Godot addon in your project.

## Steps

### 1. Get the project path

Use `$ARGUMENTS` as the Godot project path. If `$ARGUMENTS` is empty, ask the user:

> What is the path to your Godot project? (e.g. `/home/user/my-game`)

Store it as `PROJECT_PATH`.

### 2. Check Python dependencies

```bash
python -c "import mcp, websockets" 2>/dev/null || pip install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"
```

If `pip install` fails, tell the user to run it manually:
```bash
pip install -r /path/to/godot-rust-harness/requirements.txt
```

### 3. Copy the harness addon

```bash
mkdir -p "$PROJECT_PATH/addons"
cp -r "${CLAUDE_PLUGIN_ROOT}/addons/harness/" "$PROJECT_PATH/addons/harness/"
```

Confirm the copy succeeded by checking:
```bash
test -f "$PROJECT_PATH/addons/harness/harness_server.gd" && echo "Addon installed ✅"
```

### 4. Check if Autoload is registered

Read `$PROJECT_PATH/project.godot` and look for `HarnessServer`.

If **not found**, tell the user:

> Open your Godot project → **Project → Project Settings → Autoload**
>
> Add `res://addons/harness/harness_server.gd` as **HarnessServer** and enable it.
>
> Save and close the dialog.

If **found**, confirm it's already registered ✅.

### 5. Set PROJECT_ROOT

The MCP server needs to know where your Godot+Rust project is. Tell the user to add this to their project's `.mcp.json`:

```json
{
  "mcpServers": {
    "godot-rust-harness": {
      "env": {
        "PROJECT_ROOT": "/path/to/your/godot-rust-project",
        "GODOT_BIN": "godot"
      }
    }
  }
}
```

Replace `/path/to/your/godot-rust-project` with `$PROJECT_PATH`.

### 6. Done!

Tell the user setup is complete. They can now use:

- `godot_start` — launch Godot headless
- `verify()` — full build → lint → test → runtime check pipeline
- `godot_tick` / `godot_snapshot` / `godot_invariant` — granular simulation control

## Adapter (Optional)

If the project doesn't use standard node names (`SimulationEngine`, `EntityManager`), suggest creating an adapter:

```bash
cp "${CLAUDE_PLUGIN_ROOT}/examples/example_adapter.gd" \
   "$PROJECT_PATH/addons/harness/myproject_adapter.gd"
```

Then edit the file to match the project's API. The harness auto-discovers any `*_adapter.gd` in `addons/harness/`.
