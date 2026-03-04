# Harness — AI Agent Testing Addon

WebSocket JSON-RPC server for AI-assisted runtime verification of Godot projects.

## Quick Start

1. Register `harness_server.gd` as an Autoload named `HarnessServer`
2. Run Godot with `--headless` or `--harness`
3. Connect via WebSocket at `ws://127.0.0.1:9877`

## Adapter

To customize for your project, copy `examples/example_adapter.gd`
to `addons/harness/myproject_adapter.gd` and fill in the methods.

See the [main README](https://github.com/hyunlord/Godot-Rust-MCP) for full docs.

## License

MIT — see LICENSE file.
