# PROGRESS — godot-rust-harness

Work log for the godot-rust-harness MCP plugin implementation.

---

## Session 1 — 2026-03-04

### Status: COMPLETE ✅

### Completed
- [x] H-001 `src/__init__.py`
- [x] H-002 `src/godot_ws.py`
- [x] H-003 `src/server.py` (12 tools + verify composite = 13 total)
- [x] H-004 `addons/harness/plugin.cfg`
- [x] H-005 `addons/harness/harness_server.gd`
- [x] H-006 `addons/harness/harness_router.gd` (11 JSON-RPC methods)
- [x] H-007 `addons/harness/harness_invariants.gd` (7 invariants)
- [x] H-008 `requirements.txt`
- [x] H-009 `.mcp.json`
- [x] H-010 `pyproject.toml`
- [x] H-011 `tests/__init__.py` + `tests/test_server.py`
- [x] H-012 `tests/test_godot_ws.py`
- [x] H-013 `examples/smoke_test.py`
- [x] H-014 `README.md`
- [x] H-015 `PROGRESS.md`
- [x] H-016 Gate: 46/46 pytest pass, py_compile clean, all files present

### Gate results
- Python compile: ✅ server.py, godot_ws.py, test_server.py, test_godot_ws.py, smoke_test.py
- pytest: ✅ 46 passed in 1.59s
- File structure: ✅ All 16 required files present
- Smoke test: 🔵 Requires live Godot — run with `python examples/smoke_test.py`

### Architecture
- WebSocket + JSON-RPC 2.0 (Godot built-in WebSocketPeer)
- Python MCP server (src/server.py) ↔ GDScript harness (addons/harness/)
- Activates ONLY in --headless or --harness mode
- Zero production impact

---

## Session 2 — 2026-03-04

### Status: COMPLETE ✅

### Completed
- [x] P-001 `git mv CLADUE.md → CLAUDE.md` — fixes silent rules-file miss for all AI agents
- [x] P-002 `src/server.py` — 3 new MCP tools (force_event, set_config, golden_dump) + clippy step in _verify()
- [x] P-003 `tests/test_server.py` — 8 new tests (6 dispatch + 2 verify/clippy); 54 total
- [x] P-004 `.github/workflows/test.yml` — pytest on push/PR to main
- [x] P-005 `PROGRESS.md` — this entry

### Gate results
- Python compile: ✅ server.py clean
- pytest: ✅ 54 passed in 1.52s (8 new tests)
- File rename: ✅ CLAUDE.md present, CLADUE.md gone
- Tool count: ✅ 16 tools (13 original + 3 new)
- CI workflow: ✅ .github/workflows/test.yml present

### Changes summary
- `_verify()` pipeline: build → **clippy** → test → godot_start → reset → tick → invariant → stop
- New MCP tools: `godot_force_event`, `godot_set_config`, `godot_golden_dump`
- All new tools follow existing pattern: Tool definition → _dispatch case → _godot_check guard → WS proxy

---

## Session 3 — 2026-03-04

### Status: COMPLETE ✅

### Completed
- [x] G-001 `git rm addons/harness/worldsim_adapter.gd` — WorldSim-specific, deleted
- [x] G-002 `git rm addons/harness/worldsim_mapping.md` — WorldSim-specific docs, deleted
- [x] G-003 `addons/harness/harness_server.gd` — generic `_find_adapter()` discovery replaces hardcoded path
- [x] G-004 `examples/example_adapter.gd` — fully-commented adapter template created
- [x] G-005 `addons/harness/plugin.cfg` — already had correct author (no change needed)
- [x] G-006 `CLAUDE.md` — updated structure + Common Mistake #3 generalized
- [x] G-007 `AGENTS.md` — fixed plugin.cfg example (author/version/name)
- [x] G-008 `README.md` — added "Writing an Adapter" section, kept generic fallback docs
- [x] G-009 `PROGRESS.md` — this entry

### Gate results
- `python -m py_compile src/server.py` ✅
- `python -m pytest tests/ -q` ✅ 54 passed
- WorldSim refs in `addons/harness/`: 0 ✅
- WorldSim refs in `src/`, `CLAUDE.md`, `AGENTS.md`: 0 ✅
- `plugin.cfg author="godot-rust-harness"` ✅
- `examples/example_adapter.gd` exists ✅

### Changes summary
- `addons/harness/` is now a pure drop-in addon: zero project-specific code
- Adapter discovery: `_find_adapter()` scans for `*_adapter.gd`, skips `example_adapter.gd`
- Any project can integrate by copying the example adapter and filling in method bodies
- Docs generalized: README has full adapter guide, CLAUDE.md/AGENTS.md purged of WorldSim
