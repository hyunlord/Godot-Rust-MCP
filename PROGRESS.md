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

---

## Session 4 — 2026-03-04

### Status: COMPLETE ✅

### Completed
- [x] R-001 `LICENSE` — MIT license at repo root
- [x] R-002 `addons/harness/LICENSE` — copy for Godot Asset Library compliance
- [x] R-003 `.gitattributes` — export-ignore for tests/examples/docs/CI
- [x] R-004 `.mcp/server.json` — MCP Registry manifest
- [x] R-005 `addons/harness/README.md` — minimal addon README for Asset Library
- [x] R-006 `docs/PUBLISHING.md` — step-by-step guide for Godot Asset Library + MCP Registry
- [x] R-007 `README.md` — 4 badges, 3 new tools in table, clippy in verify description
- [x] R-008 `PROGRESS.md` — this entry

### Gate results
- `LICENSE` at repo root: ✅
- `addons/harness/LICENSE` (copy): ✅
- `.gitattributes` with export-ignore rules: ✅
- `.mcp/server.json` valid JSON: ✅
- `docs/PUBLISHING.md` exists: ✅
- `addons/harness/README.md` exists: ✅
- README badges present: ✅
- README simulation tools table: 10 rows (7 original + 3 new) ✅
- README verify mentions clippy: ✅
- pytest: ✅ 54 passed

### Changes summary
- MIT LICENSE enables legal use, forking, and redistribution
- `.gitattributes` ensures clean Godot Asset Library ZIP (addon + src only)
- `.mcp/server.json` manifest ready for `mcp-publisher publish` once on PyPI
- `docs/PUBLISHING.md` documents full submission workflow for both registries
- `addons/harness/` now Asset Library compliant (LICENSE + README inside addon dir)
- README badges surface CI health and license at a glance

### Confirmed limitations
- `icon.png` not yet created (required for Godot Asset Library; 128×128 PNG)
- PyPI publish required before MCP Registry listing
- Actual registry submissions are manual steps (require accounts/tokens)

---

## Session 5 — 2026-03-04

### Status: COMPLETE ✅

### Completed
- [x] D-001 `README.md` — complete rewrite for first-time Godot+Rust visitors
- [x] D-002 `PROGRESS.md` — this entry

### Gate results
- New intro ("Your AI coding assistant can't press F5"): ✅
- Quick Start section: ✅
- Zero Impact section: ✅
- Plain language tables ("What it does"): ✅
- Invariant table ("What it catches"): ✅
- No "Plutchik" jargon: ✅
- No "HEXACO" jargon: ✅
- Badges still present at top: ✅
- pytest: ✅ 54 passed

### Changes summary
- README completely rewritten (~200 lines) — problem-first framing
- Opens with "Your AI coding assistant can't press F5" hook
- Quick Start reduced from 5 steps to 3 steps
- Tool tables use plain "What it does" language instead of terse descriptions
- Invariant table says "What it catches" — no project-specific field names
- Adapter section shows real filled-in GDScript example, not just API signatures
- "Zero Impact" section reassures visitors their game is unaffected
- Architecture diagram uses plain language
- License moved to bottom of page

### Confirmed limitations
- No screenshots or GIF demos (terminal recording would strengthen discoverability)
- `icon.png` still absent (Asset Library submission prerequisite)

---

## Session 6 — 2026-03-04

### Status: COMPLETE ✅

### Context
Add Claude Code plugin system support so users can install with `/plugin install` instead of 5 manual steps.

### Tickets
| # | Title | File | Action | Depends on |
|---|-------|------|--------|------------|
| P-001 | Create plugin manifest | `.claude-plugin/plugin.json` | 🟢 DISPATCH | — |
| P-002 | Create setup command | `commands/setup.md` | 🟢 DISPATCH | — |
| P-003 | Fix .mcp.json for plugin cache | `.mcp.json` | 🔴 DIRECT | — |
| P-004 | Update README Quick Start | `README.md` | 🟢 DISPATCH | P-001 |
| P-005 | Update PROGRESS.md | `PROGRESS.md` | 🔴 DIRECT | ALL |

### Dispatch ratio: 3/5 = 60% ✅

### Completed
- [x] P-001 `.claude-plugin/plugin.json` — plugin manifest with name, version, description, author, repo, license, keywords
- [x] P-002 `commands/setup.md` — `/godot-rust-harness:setup [project-path]` command that copies addon, checks Autoload, installs pip deps, and guides PROJECT_ROOT config
- [x] P-003 `.mcp.json` — added `"cwd": "${CLAUDE_PLUGIN_ROOT}"` so server finds `src/` when installed to plugin cache
- [x] P-004 `README.md` — Quick Start now has Option A (plugin, 2 commands) + Option B (manual, collapsible `<details>`)
- [x] P-005 `PROGRESS.md` — this entry

### Gate results
- `plugin.json` valid JSON + correct name: ✅
- `commands/setup.md` exists + has frontmatter: ✅
- `.mcp.json` has `cwd: "${CLAUDE_PLUGIN_ROOT}"`: ✅
- README has `/plugin install`: ✅
- README has Option A / Option B / `<details>` collapse: ✅
- pytest: ✅ 54 passed in 1.55s (no regressions)

### Key technical decision
Used `${CLAUDE_PLUGIN_ROOT}` (official Claude Code variable) instead of `${PLUGIN_DIR}` (spec guess). Confirmed via official plugin reference docs — this variable is explicitly supported for MCP server `cwd` and `command` paths.

### Changes summary
- `/plugin install godot-rust-harness@https://github.com/hyunlord/Godot-Rust-MCP` → auto-registers MCP server, all 16 tools available immediately
- `/godot-rust-harness:setup /path/to/project` → copies addon, checks Autoload, installs deps, sets PROJECT_ROOT
- Manual setup preserved in collapsed `<details>` block for non-plugin-system users
- `cwd: "${CLAUDE_PLUGIN_ROOT}"` ensures `python -m src.server` finds the `src/` package regardless of installation directory

### Confirmed limitations
- Godot Autoload registration still requires manual step in Godot editor (no API to automate this)
- pip dependency auto-install not possible via plugin `postinstall` hook (no such event exists); setup command handles it instead
- Live `/plugin install` test requires pushing to GitHub and testing in fresh Claude Code session

---

## marketplace.json 추가 — M-001~M-003

### Context
`.claude-plugin/marketplace.json` 추가로 `/plugin marketplace add` + `/plugin install` 2줄 설치 지원.

### Tickets
| # | Title | File | Action | Depends on |
|---|-------|------|--------|------------|
| M-001 | Create marketplace.json | `.claude-plugin/marketplace.json` | 🟢 DISPATCH | — |
| M-002 | Update README Option A | `README.md` | 🟢 DISPATCH | — |
| M-003 | Update PROGRESS.md | `PROGRESS.md` | 🔴 DIRECT | ALL |

### Dispatch ratio: 2/3 = 67% ✅

### Results
- Gate: PASS
- Files changed: 3 (marketplace.json 신규, README.md 수정, PROGRESS.md 수정)
- pytest: 54 passed (no regressions)

---

## 구현 완료 보고

### 구현 의도
`/plugin marketplace add` + `/plugin install` 2줄 설치 지원

### 구현 내용
- `.claude-plugin/marketplace.json` 추가 (마켓플레이스 매니페스트)
- `README.md` Option A 수정 (marketplace add + install 방식)

### 구현 방법
oh-my-claudecode와 동일한 패턴:
레포 자체를 마켓플레이스로 등록, `source: "."` 로 루트를 플러그인으로 지정.

### 기능 설명
사용자가:
1. `/plugin marketplace add https://github.com/hyunlord/Godot-Rust-MCP`
2. `/plugin install godot-rust-harness`
이 2줄로 설치 완료. MCP 서버 자동 등록, 16개 도구 즉시 사용 가능.

### 변경된 파일 목록
- `.claude-plugin/marketplace.json` — 신규 생성
- `README.md` — Quick Start > Option A 교체
- `PROGRESS.md` — 세션 로그 추가

### 확인된 제한사항
- 실제 라이브 테스트는 GitHub push 후 새 Claude Code 세션에서 진행 필요
- Godot addon 복사 + Autoload 등록은 여전히 `/godot-rust-harness:setup` 으로 수동

---

## 자동 addon 설치 + marketplace 등록 — A-001~A-007

### Context
godot_start 호출 시 addon 자동 설치 + Autoload 자동 등록으로 사용자 경험 단순화.
`/plugin install` 2줄 설치 지원.

### Tickets
| # | Title | File | Action | Depends |
|---|-------|------|--------|---------|
| A-001 | Auto-install addon logic | `src/server.py` | 🟢 DISPATCH | — |
| A-002 | Auto-install tests | `tests/test_server.py` | 🟢 DISPATCH | A-001 |
| A-003 | Create marketplace.json | `.claude-plugin/marketplace.json` | 🟢 DISPATCH | — |
| A-004 | Delete setup command | `commands/setup.md`, `commands/` | 🔴 DIRECT | — |
| A-005 | Update plugin.json | `.claude-plugin/plugin.json` | 🔴 DIRECT | — |
| A-006 | Update README Quick Start | `README.md` | 🟢 DISPATCH | — |
| A-007 | Update PROGRESS.md | `PROGRESS.md` | 🔴 DIRECT | ALL |

### Dispatch ratio: 4/7 = 57% (A-004, A-005 trivial/direct justified)

### Results
- Gate: PASS
- pytest: 60 passed (54 original + 6 new)
- Files changed: src/server.py, tests/test_server.py, .claude-plugin/marketplace.json, README.md, PROGRESS.md
- Deleted: commands/setup.md, commands/

---

## 구현 완료 보고

### 구현 의도
godot_start 호출 시 addon 자동 설치 + 마켓플레이스 등록으로 사용자 경험 단순화

### 구현 내용
- `src/server.py`: `_ensure_addon_installed()` + `_ensure_autoload()` 추가
  → godot_start 시 addons/harness/ 없으면 자동 복사 + project.godot에 Autoload 등록
- `.claude-plugin/marketplace.json`: 마켓플레이스 매니페스트 (이미 존재)
- `commands/setup.md`: 삭제 (자동 설치로 대체)
- `README.md`: Quick Start에서 setup 커맨드 제거, "자동 설치" 메시지 추가
- `tests/test_server.py`: 자동 설치 관련 테스트 6개 추가

### 구현 방법
- addon 설치: shutil.copy2로 파일별 복사, harness_server.gd 존재 여부로 설치 판단
- Autoload 등록: project.godot를 텍스트로 읽어서 [autoload] 섹션에 항목 추가
- 멱등성: 이미 존재하면 스킵, 기존 파일 절대 덮어쓰지 않음

### 기능 설명
사용자 경험:
1. /plugin marketplace add https://github.com/hyunlord/Godot-Rust-MCP
2. /plugin install godot-rust-harness
3. godot_start 호출 → addon 자동 설치 → 바로 사용
수동 파일 복사, Autoload 등록 불필요.

### 확인된 제한사항
- project.godot INI 파싱이 단순 문자열 치환이므로 극단적 edge case에서 깨질 수 있음
  (예: 주석 안에 [autoload]가 있는 경우 — 실제로는 거의 발생 안 함)
- 기존 harness 파일이 있으면 업데이트 안 함 (의도적 — 사용자 수정 보존)
