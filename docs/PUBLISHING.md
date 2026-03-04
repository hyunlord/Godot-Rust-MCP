# Publishing Guide

How to list godot-rust-harness on Godot Asset Library and MCP Registry.

---

## Godot Asset Library

### Prerequisites
- Godot account (https://godotengine.org/asset-library/asset/submit)
- This repo must be public on GitHub

### Steps

1. **Go to** https://godotengine.org/asset-library/asset/submit
2. **Fill in the form:**

| Field | Value |
|-------|-------|
| Title | Godot Rust Harness |
| Category | Addons → Tools |
| Godot version | 4.2 |
| Version | 1.0.0 |
| Repository host | GitHub |
| Repository | hyunlord/Godot-Rust-MCP |
| Download commit | (paste latest commit hash from `main`) |
| Icon URL | `https://raw.githubusercontent.com/hyunlord/Godot-Rust-MCP/main/icon.png` |
| License | MIT |
| Description | (see below) |

3. **Description** (paste this):

```
MCP plugin that gives AI coding agents (Claude Code, Codex) the ability to
launch Godot headless, advance simulation ticks, query entity state, run
invariant checks, and benchmark performance.

Features:
- 16 MCP tools: cargo build/test/clippy + Godot tick/snapshot/query/invariant/bench
- One-call verify() pipeline: build → clippy → test → godot → invariant
- 7 built-in invariants for simulation value bounds checking
- Adapter pattern for project-specific API mapping
- Zero impact on normal gameplay (headless/--harness mode only)

Installation:
1. Copy addons/harness/ to your project
2. Register HarnessServer as Autoload
3. Point the MCP server at your project via .mcp.json
```

4. **Submit** and wait for review (usually 1-3 days)

### Icon
You need a 128×128 PNG icon. Create or commission one and put it at repo root
as `icon.png`. For now you can use a placeholder.

### Updating
When you release a new version:
1. Push changes to `main`
2. Go to your asset page → Edit → update commit hash and version number

---

## MCP Registry

### Prerequisites
- GitHub account
- `mcp-publisher` CLI installed
- Package published to PyPI (the registry stores metadata, not code)

### Step 1: Publish to PyPI

```bash
# Build the package
pip install build twine
python -m build

# Upload to PyPI
twine upload dist/*
```

You need a PyPI account and API token. Set up `~/.pypirc` or use
`TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-xxx twine upload dist/*`.

### Step 2: Install mcp-publisher

```bash
# macOS/Linux via Homebrew
brew install mcp-publisher

# Or direct download
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/
```

### Step 3: Authenticate

```bash
mcp-publisher login github
# Follow the prompts — open the URL, enter the code
```

This grants publish rights to the `io.github.hyunlord/*` namespace.

### Step 4: Publish

```bash
mcp-publisher publish --file=.mcp/server.json
```

Expected output:
```
Publishing to https://registry.modelcontextprotocol.io...
✓ Successfully published
✓ Server io.github.hyunlord/godot-rust-harness version 1.0.0
```

### Step 5: Verify

```bash
curl "https://registry.modelcontextprotocol.io/v0/servers?search=godot-rust-harness"
```

Should return your server metadata.

### Updating
When you release a new version:
1. Update version in `pyproject.toml`, `.mcp/server.json`, and `addons/harness/plugin.cfg`
2. Publish new version to PyPI
3. Run `mcp-publisher publish --file=.mcp/server.json`

---

## GitHub Repository Settings

While you're at it, set these in the GitHub repo settings:

### Description
```
MCP plugin for AI-assisted runtime verification of Godot+Rust projects
```

### Topics (tags)
```
godot, godot4, rust, mcp, model-context-protocol, claude-code,
testing, simulation, game-development, ai-tools
```

### About → Website
```
https://registry.modelcontextprotocol.io/
```
