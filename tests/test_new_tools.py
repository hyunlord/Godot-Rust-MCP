"""Tests for Phase 1 new tools: rust_analyze, rust_dependencies, crate_map,
project_overview, diagnose, build_explain."""
import json
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tools.analysis import rust_analyze, rust_dependencies, crate_map
from src.tools.structure import project_overview
from src.tools.diagnose import diagnose, build_explain


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


# ── rust_analyze ─────────────────────────────────────────────────────────────

class TestRustAnalyze:
    def test_detects_unwrap_in_production_code(self, tmp_path: Path):
        rs_file = tmp_path / "lib.rs"
        rs_file.write_text('fn foo() { let x = some_opt.unwrap(); }\n')

        clippy_json = json.dumps({"reason": "build-finished", "success": True})
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, clippy_json)):
            result = rust_analyze(tmp_path, checks=["unwrap"])

        assert result["summary"]["total_issues"] >= 1
        unwrap_issues = [i for i in result["issues"] if i["check"] == "unwrap"]
        assert len(unwrap_issues) >= 1
        assert unwrap_issues[0]["line"] == 1

    def test_skips_unwrap_in_test_file(self, tmp_path: Path):
        rs_file = tmp_path / "test_foo.rs"
        rs_file.write_text('fn test_it() { let x = opt.unwrap(); }\n')

        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, "")):
            result = rust_analyze(tmp_path, checks=["unwrap"])

        unwrap_issues = [i for i in result["issues"] if i["check"] == "unwrap"]
        assert len(unwrap_issues) == 0

    def test_detects_unsafe_without_safety_comment(self, tmp_path: Path):
        rs_file = tmp_path / "lib.rs"
        rs_file.write_text('fn foo() {\n    unsafe { *ptr = 1; }\n}\n')

        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, "")):
            result = rust_analyze(tmp_path, checks=["unsafe"])

        unsafe_issues = [i for i in result["issues"] if i["check"] == "unsafe"]
        assert len(unsafe_issues) >= 1

    def test_detects_clone_heavy(self, tmp_path: Path):
        rs_file = tmp_path / "lib.rs"
        rs_file.write_text('fn foo() { let x = a.clone().clone().foo(); }\n')

        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, "")):
            result = rust_analyze(tmp_path, checks=["clone_heavy"])

        clone_issues = [i for i in result["issues"] if i["check"] == "clone_heavy"]
        assert len(clone_issues) >= 1

    def test_clippy_json_parsed(self, tmp_path: Path):
        clippy_output = json.dumps({
            "reason": "compiler-message",
            "message": {
                "level": "warning",
                "message": "unused variable `x`",
                "code": None,
                "spans": [{"file_name": "src/lib.rs", "line_start": 5}],
                "rendered": "warning: unused variable",
            },
        })
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, clippy_output)):
            result = rust_analyze(tmp_path, checks=[])

        clippy_issues = [i for i in result["issues"] if i["check"] == "clippy"]
        assert len(clippy_issues) == 1
        assert clippy_issues[0]["line"] == 5

    def test_summary_structure(self, tmp_path: Path):
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, "")):
            result = rust_analyze(tmp_path, checks=[])

        assert "summary" in result
        assert "total_issues" in result["summary"]
        assert "by_severity" in result["summary"]
        assert "by_check" in result["summary"]


# ── rust_dependencies ─────────────────────────────────────────────────────────

class TestRustDependencies:
    def test_returns_tree_output(self, tmp_path: Path):
        tree_output = "0 my-crate v0.1.0\n1 tokio v1.0\n"
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, tree_output)):
            result = rust_dependencies(tmp_path)

        assert result["dependency_tree"] == tree_output

    def test_handles_cargo_tree_failure(self, tmp_path: Path):
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(1, "", "error")):
            result = rust_dependencies(tmp_path)

        assert result["dependency_tree"] is None
        assert "tree_error" in result

    def test_parses_direct_deps_from_cargo_toml(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text(
            "[package]\nname = \"foo\"\n\n[dependencies]\ntokio = \"1\"\nserde = \"1\"\n"
        )
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, "")):
            result = rust_dependencies(tmp_path)

        assert "tokio" in result["direct_dependencies"]
        assert "serde" in result["direct_dependencies"]

    def test_outdated_note_when_not_installed(self, tmp_path: Path):
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(1, "", "not found")):
            result = rust_dependencies(tmp_path)

        assert "outdated_note" in result


# ── crate_map ─────────────────────────────────────────────────────────────────

class TestCrateMap:
    def _make_meta(self, crates: list[dict]) -> str:
        packages = []
        ids = []
        for c in crates:
            pkg_id = f"{c['name']} 0.1.0 (path+file:///fake/{c['name']})"
            ids.append(pkg_id)
            packages.append({
                "id": pkg_id,
                "name": c["name"],
                "version": "0.1.0",
                "manifest_path": f"/fake/{c['name']}/Cargo.toml",
                "dependencies": [
                    {"name": d, "optional": False} for d in c.get("deps", [])
                ],
                "targets": [{"crate_types": ["lib"]}],
            })
        return json.dumps({"packages": packages, "workspace_members": ids})

    def test_text_format(self, tmp_path: Path):
        meta = self._make_meta([{"name": "core"}, {"name": "engine", "deps": ["core"]}])
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, meta)):
            with patch("src.tools.structure.subprocess.run", return_value=make_proc(0, meta)):
                from src.tools.analysis import crate_map as cm
                result = cm(tmp_path, "text")

        assert result["format"] == "text"
        assert "graph" in result
        assert result["crate_count"] == 2

    def test_mermaid_format(self, tmp_path: Path):
        meta = self._make_meta([{"name": "core"}, {"name": "engine", "deps": ["core"]}])
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(0, meta)):
            from src.tools.analysis import crate_map as cm
            result = cm(tmp_path, "mermaid")

        assert "graph TD" in result["graph"]
        assert result["format"] == "mermaid"

    def test_handles_cargo_metadata_failure(self, tmp_path: Path):
        with patch("src.tools.analysis.subprocess.run", return_value=make_proc(1, "", "error")):
            result = crate_map(tmp_path)

        assert "error" in result


# ── project_overview ──────────────────────────────────────────────────────────

class TestProjectOverview:
    def _make_meta(self) -> str:
        pkg_id = "my-game 0.1.0 (path+file:///fake/my-game)"
        return json.dumps({
            "packages": [{
                "id": pkg_id,
                "name": "my-game",
                "version": "0.1.0",
                "manifest_path": "/fake/my-game/Cargo.toml",
                "dependencies": [],
                "targets": [{"crate_types": ["cdylib"]}],
            }],
            "workspace_members": [pkg_id],
        })

    def test_returns_all_sections(self, tmp_path: Path):
        with patch("src.tools.structure.subprocess.run", return_value=make_proc(0, self._make_meta())):
            result = project_overview(tmp_path)

        assert "rust_workspace" in result
        assert "godot_project" in result
        assert "bridge" in result
        assert "health" in result

    def test_finds_project_godot(self, tmp_path: Path):
        (tmp_path / "project.godot").write_text("[gd_resource]\nconfig_version=5\n")
        with patch("src.tools.structure.subprocess.run", return_value=make_proc(0, self._make_meta())):
            result = project_overview(tmp_path)

        assert result["godot_project"]["path"] is not None

    def test_detects_autoloads(self, tmp_path: Path):
        (tmp_path / "project.godot").write_text(
            '[autoload]\n\nHarnessServer="*res://addons/harness/harness_server.gd"\n'
        )
        with patch("src.tools.structure.subprocess.run", return_value=make_proc(0, self._make_meta())):
            result = project_overview(tmp_path)

        autoloads = result["godot_project"]["autoloads"]
        assert any(a["name"] == "HarnessServer" for a in autoloads)

    def test_scans_gdext_classes(self, tmp_path: Path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "bridge.rs").write_text(textwrap.dedent("""\
            #[derive(GodotClass)]
            #[class(base=Node)]
            struct SimBridge {
                base: Base<Node>,
            }
            #[godot_api]
            impl SimBridge {
                #[func]
                pub fn tick(&mut self, n: i32) -> Dictionary {
                    Dictionary::new()
                }
            }
        """))
        with patch("src.tools.structure.subprocess.run", return_value=make_proc(0, self._make_meta())):
            result = project_overview(tmp_path)

        classes = result["bridge"]["gdextension_classes"]
        assert any(c["struct_name"] == "SimBridge" for c in classes)

    def test_health_missing_configs(self, tmp_path: Path):
        with patch("src.tools.structure.subprocess.run", return_value=make_proc(1, "", "no cargo")):
            result = project_overview(tmp_path)

        assert isinstance(result["health"]["missing_configs"], list)


# ── diagnose ──────────────────────────────────────────────────────────────────

class TestDiagnose:
    def test_matches_gd_type_error(self):
        result = diagnose("cannot find type `Gd` in this scope")
        assert result["error_type"] == "missing_import"
        assert len(result["solutions"]) >= 1
        assert "godot::prelude" in result["solutions"][0]["code_change"]

    def test_matches_borrow_error(self):
        result = diagnose("already borrowed: BorrowMutError")
        assert result["error_type"] == "borrow_conflict"

    def test_matches_gdextension_config_error(self):
        result = diagnose("Can't load GDExtension config from path")
        assert "gdextension" in result["error_type"].lower() or result["root_cause"] != ""

    def test_unknown_error_returns_fallback(self):
        result = diagnose("some completely unknown error xyz123")
        assert result["error_type"] == "unknown"
        assert len(result["solutions"]) >= 1

    def test_auto_context_detection_build(self):
        result = diagnose("error[E0308]: mismatched types")
        assert result["context"] == "build"

    def test_auto_context_detection_godot(self):
        result = diagnose("Can't load GDExtension config")
        assert result["context"] == "godot"


# ── build_explain ─────────────────────────────────────────────────────────────

class TestBuildExplain:
    def test_success_build(self, tmp_path: Path):
        finished = json.dumps({"reason": "build-finished", "success": True})
        with patch("src.tools.diagnose.subprocess.run", return_value=make_proc(0, finished)):
            result = build_explain(tmp_path)

        assert result["success"] is True
        assert result["errors"] == []

    def test_parses_compiler_error(self, tmp_path: Path):
        error_msg = json.dumps({
            "reason": "compiler-message",
            "message": {
                "level": "error",
                "message": "mismatched types",
                "code": {"code": "E0308"},
                "spans": [{"file_name": "src/lib.rs", "line_start": 10}],
                "rendered": "error[E0308]",
            },
        })
        with patch("src.tools.diagnose.subprocess.run", return_value=make_proc(1, error_msg)):
            result = build_explain(tmp_path)

        assert result["success"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["error_code"] == "E0308"
        assert "Type mismatch" in result["errors"][0]["explanation"]

    def test_cargo_not_found(self, tmp_path: Path):
        with patch("src.tools.diagnose.subprocess.run", side_effect=FileNotFoundError):
            result = build_explain(tmp_path)

        assert result["success"] is False
        assert "cargo not found" in result["error"]

    def test_returns_fix_suggestion_for_known_code(self, tmp_path: Path):
        error_msg = json.dumps({
            "reason": "compiler-message",
            "message": {
                "level": "error",
                "message": "use of moved value",
                "code": {"code": "E0382"},
                "spans": [{"file_name": "src/main.rs", "line_start": 5}],
                "rendered": "",
            },
        })
        with patch("src.tools.diagnose.subprocess.run", return_value=make_proc(1, error_msg)):
            result = build_explain(tmp_path)

        assert result["errors"][0]["fix_suggestion"] != ""
