# CLAUDE.md — godot-rust-harness

> MCP plugin that lets Claude Code verify Godot+Rust simulation projects at runtime.
> This file governs ALL work in this repository.

---

## Project Identity

- **Name**: godot-rust-harness
- **Purpose**: MCP server + Godot addon that enables AI agents (Claude Code, Codex) to build → test → run → verify Godot+Rust projects without human intervention
- **Language**: Python (MCP server) + GDScript (Godot addon)
- **Target users**: AI coding agents working on Godot+Rust simulation projects
- **This is NOT a game** — it is developer tooling. No end-user UI, no localization of display text.

---

## Architecture — Do Not Violate

```
Claude Code / Codex
    │
    │  MCP Protocol (stdio, JSON)
    │
┌───▼──────────────────────────────────┐
│  Python MCP Server                    │
│  src/server.py                        │
│                                       │
│  Tools:                               │
│  ├─ rust_build / rust_test / clippy   │  ← subprocess: cargo
│  ├─ godot_start / godot_stop          │  ← subprocess: godot --headless
│  ├─ godot_tick / snapshot / query     │  ← WebSocket → Harness
│  ├─ godot_invariant / bench / reset   │  ← WebSocket → Harness
│  └─ verify (composite)               │  ← all-in-one pipeline
└───┬───────────────────┬──────────────┘
    │ subprocess         │ WebSocket (ws://127.0.0.1:9877)
    ▼                    ▼
  cargo CLI           Godot --headless
                      ┌────────────────────┐
                      │ addons/harness/     │
                      │ HarnessServer       │
                      │ (GDScript addon)    │
                      │ JSON-RPC 2.0        │
                      └────────────────────┘
```

### Two deliverables
1. **Godot addon** (`addons/harness/`) — drop into any Godot 4.x project
2. **Python MCP server** (`src/`) — register in `.mcp.json`, Claude Code calls tools

---

## Repository Structure

```
godot-rust-harness/
├── CLAUDE.md                          ← you are here
├── AGENTS.md                          ← implementor behavior rules
├── README.md                          ← user-facing docs
├── .mcp.json                          ← MCP server registration
├── pyproject.toml                     ← Python project config
├── requirements.txt                   ← mcp, websockets
│
├── src/                               ← Python MCP server
│   ├── __init__.py
│   ├── server.py                      ← entry point, tool definitions
│   └── godot_ws.py                    ← WebSocket client to Godot harness
│
├── addons/
│   └── harness/                       ← Godot addon (copy to target project)
│       ├── plugin.cfg                 ← Godot addon manifest
│       ├── harness_server.gd          ← WebSocket server (Autoload)
│       ├── harness_router.gd          ← command dispatch
│       └── harness_invariants.gd      ← invariant checker (extensible)
│
├── tests/
│   ├── test_server.py                 ← MCP server unit tests
│   ├── test_godot_ws.py               ← WebSocket client tests
│   └── test_invariants.py             ← invariant logic tests (mock)
│
├── examples/
│   ├── smoke_test.py                  ← end-to-end smoke test script
│   └── example_adapter.gd            ← adapter template (copy to your project)
│
└── PROGRESS.md                        ← work log (append-only)
```

---

## Coding Standards

### Python (src/, tests/)
- Python 3.11+
- Type hints on ALL function signatures — no bare `def f(x):`
- `async/await` for all I/O (WebSocket, subprocess)
- `asyncio.run()` as single entry point
- Error handling: every MCP tool returns JSON, never raises to caller
- Max function length: 50 lines. Extract helpers if longer.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes

### GDScript (addons/harness/)
- Godot 4.2+ compatible
- Static typing everywhere: `var x: int = 0`, `func f(n: int) -> Dictionary:`
- Class names: `HarnessServer`, `HarnessRouter`, `HarnessInvariants`
- Constants: `UPPER_SNAKE_CASE`
- All log messages prefixed with `[Harness]`
- No user-facing UI text — this is dev tooling
- No `Locale`, no `tr()`, no i18n — not applicable to this project

### Localization policy
This project has **NO localized text**. All output is:
- JSON over WebSocket (machine-readable)
- Python stdout/stderr (English, dev-only)
- GDScript `print()` / `push_error()` (English, dev-only, prefixed `[Harness]`)

If a future version adds user-visible UI (debug overlay, etc.), THEN add i18n.
Until then: English everywhere, no locale infrastructure needed.

### Documentation
- README.md: installation, usage, tool reference
- Docstrings on every public function (Python) and exported function (GDScript)
- PROGRESS.md: append-only work log

---

## Dispatch Rules

### Workflow: Ralph Loop

Every feature request follows this cycle:

```
1. PLAN    — Split into tickets. Each ticket = 1 file or 1 concern.
2. LOG     — Write ticket table in PROGRESS.md BEFORE any code.
3. CLASSIFY — Mark each ticket 🟢 DISPATCH (ask_codex) or 🔴 DIRECT.
4. EXECUTE — Dispatch first, then DIRECT for integration.
5. VERIFY  — Run gate. Log results in PROGRESS.md.
6. REPEAT  — Next batch.
```

### Dispatch ratio: ≥60% DISPATCH mandatory

If your ticket table has <60% dispatch → re-split until it does.

### DIRECT is ONLY allowed when ALL THREE conditions are true:
1. The change touches shared interfaces (multiple files must change atomically)
2. The change is <50 lines total
3. No single-file alternative exists

### DISPATCH tool routing
- `ask_codex` — for all dispatched tickets
- Before every dispatch: confirm (a) single file target, (b) no shared-state mutation, (c) clear acceptance criteria

### PROGRESS.md format

```markdown
## [Feature Name] — [Ticket Range]

### Context
[1-2 sentences]

### Tickets
| # | Title | File | Action | Depends on |
|---|-------|------|--------|------------|
| 1 | ... | src/server.py | 🟢 DISPATCH | — |
| 2 | ... | src/godot_ws.py | 🟢 DISPATCH | — |
| 3 | ... | .mcp.json | 🔴 DIRECT | 1 |

### Dispatch ratio: X/Y = ZZ% ✅/❌

### Results
- Gate: PASS / FAIL
- Files changed: N
```

---

## Gate

Before marking any batch complete, run:

```bash
# Python
python -m py_compile src/server.py
python -m py_compile src/godot_ws.py
python -m pytest tests/ -q

# GDScript (if Godot available)
# godot --headless --path test_project/ --quit
```

Gate MUST pass. No exceptions. If gate fails, fix before proceeding.

---

## Common Mistakes — NEVER Do These

1. **Putting game logic in this repo** — this is a dev tool, not a game
2. **Adding localization/i18n** — no user-facing text exists
3. **Hardcoding project-specific paths** — this plugin must be generic for any Godot+Rust project; put project-specific code in your own `*_adapter.gd` inside your project's copy of `addons/harness/`
4. **Skipping type hints in Python** — every function signature needs types
5. **Using `Task` tool for code changes** — ALWAYS dispatch via `ask_codex`
6. **Skipping PROGRESS.md** — log BEFORE coding, not after
7. **Making harness active in normal Godot runs** — ONLY in `--headless` or `--harness` mode
8. **Blocking the Godot main thread** — WebSocket handling must be non-blocking in `_process()`
9. **Returning raw exceptions from MCP tools** — always return `{"error": "message"}` JSON
10. **Assuming SimulationEngine/EntityManager exist** — harness must gracefully handle missing nodes

---

## Testing

### Unit tests (tests/)
- Python: pytest with asyncio support
- Mock WebSocket for godot_ws tests
- Mock subprocess for cargo tool tests
- Each MCP tool has at least one test

### Smoke test (examples/smoke_test.py)
- Requires a running Godot project with harness addon
- Tests: ping → tick → snapshot → invariant → scene_tree
- Pass criteria: all 5 return valid JSON, no errors

### Manual verification
- Install addon in a Godot project
- Run `godot --headless --harness`
- Connect with `websocat ws://127.0.0.1:9877`
- Send `{"jsonrpc":"2.0","id":1,"method":"ping","params":{}}`
- Expect `{"jsonrpc":"2.0","id":1,"result":{"pong":true,...}}`