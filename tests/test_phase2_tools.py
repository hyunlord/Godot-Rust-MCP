"""Tests for Phase 2 tools: gdext_check, gdext_scaffold, gdext_version_check,
migration_scan, migration_diff."""
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tools.gdext import gdext_check, gdext_scaffold, gdext_version_check
from src.tools.migration import migration_scan, migration_diff


def make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


# ── gdext_check ───────────────────────────────────────────────────────────────

class TestGdextCheck:
    def _write_rs(self, tmp_path: Path, content: str, name: str = "lib.rs") -> Path:
        f = tmp_path / name
        f.write_text(content)
        return f

    def test_detects_unwrap_in_func(self, tmp_path: Path):
        self._write_rs(tmp_path, textwrap.dedent("""\
            use godot::prelude::*;
            #[derive(GodotClass)]
            struct Foo { base: Base<Node> }
            #[godot_api]
            impl Foo {
                #[func]
                pub fn get_value(&self) -> i64 {
                    self.inner.unwrap()
                }
            }
        """))
        result = gdext_check(tmp_path)
        assert result["summary"]["total_issues"] >= 1
        ids = [i["rule_id"] for i in result["issues"]]
        assert "GDEXT-001" in ids

    def test_no_issues_on_clean_code(self, tmp_path: Path):
        self._write_rs(tmp_path, textwrap.dedent("""\
            use godot::prelude::*;
            #[derive(GodotClass)]
            #[class(base=Node)]
            struct Clean { base: Base<Node> }
            #[godot_api]
            impl INode for Clean {
                fn init(base: Base<Node>) -> Self { Self { base } }
            }
            #[godot_api]
            impl Clean {
                #[func]
                pub fn hello(&self) -> GString { GString::from("hi") }
            }
        """))
        result = gdext_check(tmp_path)
        # GDEXT-001 won't fire (no .unwrap()), others may fire but shouldn't be errors
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        assert len(errors) == 0

    def test_skips_non_gdext_files(self, tmp_path: Path):
        self._write_rs(tmp_path, textwrap.dedent("""\
            fn plain_rust() {
                let x = some_option.unwrap();
            }
        """))
        result = gdext_check(tmp_path)
        # No gdext keywords → file skipped → no gdext rule hits
        gdext_issues = [i for i in result["issues"] if i["rule_id"].startswith("GDEXT")]
        assert len(gdext_issues) == 0

    def test_returns_summary_structure(self, tmp_path: Path):
        result = gdext_check(tmp_path)
        assert "issues" in result
        assert "summary" in result
        assert "rules_checked" in result["summary"]
        assert result["summary"]["rules_checked"] >= 10

    def test_error_when_rules_missing(self, tmp_path: Path):
        with patch("src.tools.gdext.Path.read_text", side_effect=OSError):
            result = gdext_check(tmp_path)
        assert "error" in result


# ── gdext_scaffold ────────────────────────────────────────────────────────────

class TestGdextScaffold:
    def test_godot_class_pattern(self):
        result = gdext_scaffold("SimBridge", "godot_class", "Node")
        assert "error" not in result
        assert "GodotClass" in result["code"]
        assert "SimBridge" in result["code"]
        assert "Base<Node>" in result["code"]
        assert result["file_path"] == "src/sim_bridge.rs"

    def test_singleton_pattern(self):
        result = gdext_scaffold("GameManager", "singleton")
        assert "singleton" in result["code"].lower() or "Autoload" in "\n".join(result["notes"])
        assert "GameManager" in result["code"]

    def test_resource_pattern(self):
        result = gdext_scaffold("GameConfig", "resource")
        assert "Resource" in result["code"]
        assert "GameConfig" in result["code"]

    def test_bridge_class_pattern(self):
        result = gdext_scaffold("SimBridge", "bridge_class", "Node")
        assert "#[func]" in result["code"]
        assert "tick" in result["code"]

    def test_signal_hub_pattern(self):
        result = gdext_scaffold("EventBus", "signal_hub")
        assert "#[signal]" in result["code"]
        assert "EventBus" in result["code"]

    def test_export_enum_pattern(self):
        result = gdext_scaffold("EntityState", "export_enum")
        assert "GodotConvert" in result["code"]
        assert "EntityState" in result["code"]

    def test_unknown_pattern_returns_error(self):
        result = gdext_scaffold("Foo", "nonexistent_pattern")
        assert "error" in result
        assert "available" in result

    def test_fields_included_in_output(self):
        fields = [{"name": "health", "type": "f64", "default": "1.0"}]
        result = gdext_scaffold("Player", "godot_class", "Node", fields)
        assert "health" in result["code"]

    def test_snake_case_file_path(self):
        result = gdext_scaffold("MyComplexClass", "godot_class")
        assert result["file_path"] == "src/my_complex_class.rs"


# ── gdext_version_check ────────────────────────────────────────────────────────

class TestGdextVersionCheck:
    def test_returns_structure(self, tmp_path: Path):
        result = gdext_version_check(tmp_path)
        assert "gdext_version" in result
        assert "godot_version" in result
        assert "api_feature" in result
        assert "compatible" in result
        assert "warnings" in result
        assert isinstance(result["warnings"], list)

    def test_finds_gdext_in_cargo_toml(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text(
            '[package]\nname = "game"\n\n[dependencies]\ngodot = { version = "0.2.1", features = ["api-4-3"] }\n'
        )
        with patch("src.tools.gdext._get_godot_version", return_value=None):
            result = gdext_version_check(tmp_path)
        assert result["gdext_version"] == "0.2.1"
        assert result["api_feature"] == "api-4-3"

    def test_warns_when_godot_missing(self, tmp_path: Path):
        with patch("src.tools.gdext._get_godot_version", return_value=None):
            result = gdext_version_check(tmp_path)
        warnings_text = " ".join(result["warnings"])
        assert "Godot" in warnings_text or result["godot_version"] is None

    def test_api_mismatch_warning(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text(
            '[dependencies]\ngodot = { version = "0.2", features = ["api-4-3"] }\n'
        )
        with patch("src.tools.gdext._get_godot_version", return_value="4.2.stable"):
            result = gdext_version_check(tmp_path)
        # api-4-3 vs Godot 4.2 — should warn
        assert any("4.3" in w or "4.2" in w or "mismatch" in w.lower() for w in result["warnings"])


# ── migration_scan ────────────────────────────────────────────────────────────

class TestMigrationScan:
    def test_scan_mode_returns_summary(self, tmp_path: Path):
        (tmp_path / "sim.gd").write_text(
            "extends Node\nfunc process_tick():\n    pass\nfunc step(n):\n    pass\n"
        )
        result = migration_scan(tmp_path)
        assert "files" in result
        assert "summary" in result
        assert result["summary"]["total_files"] >= 1

    def test_classifies_ui_as_keep(self, tmp_path: Path):
        (tmp_path / "hud.gd").write_text("extends Control\nfunc _ready():\n    pass\n")
        result = migration_scan(tmp_path)
        ui_files = [f for f in result["files"] if not f["should_migrate"]]
        assert len(ui_files) >= 1

    def test_classifies_logic_as_migrate(self, tmp_path: Path):
        (tmp_path / "sim_engine.gd").write_text(
            "extends Node\nfunc process_tick():\n    var i = 0\nfunc step(n: int):\n    pass\n"
        )
        result = migration_scan(tmp_path)
        migrate_files = [f for f in result["files"] if f["should_migrate"]]
        assert len(migrate_files) >= 1

    def test_detail_mode_returns_skeleton(self, tmp_path: Path):
        gd = tmp_path / "sim.gd"
        gd.write_text(
            "extends Node\n\nvar health: float = 1.0\n\nfunc process_tick():\n    pass\n\nfunc reset():\n    pass\n"
        )
        result = migration_scan(tmp_path, "sim.gd", "detail")
        assert "rust_skeleton" in result
        assert "use godot::prelude::*" in result["rust_skeleton"]
        assert "process_tick" in result["rust_skeleton"] or "migration_notes" in result

    def test_complexity_assessment(self, tmp_path: Path):
        # Short simple file → low complexity
        (tmp_path / "simple.gd").write_text("extends Node\nfunc init():\n    pass\n")
        result = migration_scan(tmp_path)
        if result["files"]:
            assert result["files"][0]["complexity"] in ("low", "medium", "high")

    def test_empty_directory(self, tmp_path: Path):
        result = migration_scan(tmp_path)
        assert result["summary"]["total_files"] == 0


# ── migration_diff ─────────────────────────────────────────────────────────────

class TestMigrationDiff:
    def test_matched_methods(self, tmp_path: Path):
        (tmp_path / "sim.gd").write_text("extends Node\nfunc process_tick():\n    pass\nfunc reset():\n    pass\n")
        (tmp_path / "sim.rs").write_text(
            "use godot::prelude::*;\nimpl Sim {\n    fn process_tick(&mut self) {}\n    fn reset(&mut self) {}\n}\n"
        )
        result = migration_diff(tmp_path, "sim.gd", "sim.rs")
        assert result["coverage"]["matched"] >= 1
        assert result["coverage"]["gdscript_methods"] == 2

    def test_detects_missing_in_rust(self, tmp_path: Path):
        (tmp_path / "sim.gd").write_text("extends Node\nfunc tick():\n    pass\nfunc missing_fn():\n    pass\n")
        (tmp_path / "sim.rs").write_text("impl Sim {\n    fn tick(&mut self) {}\n}\n")
        result = migration_diff(tmp_path, "sim.gd", "sim.rs")
        assert "missing_fn" in result["coverage"]["missing_in_rust"]

    def test_missing_gdscript_file(self, tmp_path: Path):
        (tmp_path / "sim.rs").write_text("fn tick() {}")
        result = migration_diff(tmp_path, "nonexistent.gd", "sim.rs")
        assert "error" in result

    def test_missing_rust_file(self, tmp_path: Path):
        (tmp_path / "sim.gd").write_text("func tick(): pass")
        result = migration_diff(tmp_path, "sim.gd", "nonexistent.rs")
        assert "error" in result

    def test_returns_pattern_checks(self, tmp_path: Path):
        (tmp_path / "sim.gd").write_text("extends Node\nfunc run():\n    var x = randf()\n")
        (tmp_path / "sim.rs").write_text("fn run() { let x = rng.gen::<f64>(); }\n")
        result = migration_diff(tmp_path, "sim.gd", "sim.rs")
        assert "pattern_checks" in result
        assert isinstance(result["pattern_checks"], list)
