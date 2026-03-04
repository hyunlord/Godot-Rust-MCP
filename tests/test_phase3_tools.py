"""Tests for Phase 3 tools: perf_suggest, rust_unsafe_audit, migration_validate."""
import textwrap
from pathlib import Path

import pytest

from src.tools.performance import perf_suggest, rust_unsafe_audit, migration_validate


# ── perf_suggest ──────────────────────────────────────────────────────────────

class TestPerfSuggest:
    def test_detects_hashmap(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text("use std::collections::HashMap;\nlet m: HashMap<u64, Entity> = HashMap::new();\n")
        result = perf_suggest(tmp_path)
        mem_suggestions = [s for s in result["suggestions"] if s["rule_id"] == "PERF-MEM-003"]
        assert len(mem_suggestions) >= 1

    def test_detects_string_by_value(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text("fn process(name: String) -> String { name }\n")
        result = perf_suggest(tmp_path)
        str_suggestions = [s for s in result["suggestions"] if s["rule_id"] == "PERF-MEM-002"]
        assert len(str_suggestions) >= 1

    def test_detects_box_dyn(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text("struct Foo { handler: Box<dyn FnMut()> }\n")
        result = perf_suggest(tmp_path)
        box_suggestions = [s for s in result["suggestions"] if s["rule_id"] == "PERF-MEM-004"]
        assert len(box_suggestions) >= 1

    def test_focus_filter(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text(
            "use std::collections::HashMap;\nlet m: HashMap<u32, f64> = HashMap::new();\n"
            "fn f(s: String) {}\n"
        )
        result = perf_suggest(tmp_path, focus="memory")
        categories = {s["category"] for s in result["suggestions"]}
        assert categories <= {"memory"}

    def test_deduplicates_same_rule_per_file(self, tmp_path: Path):
        # Multiple HashMap lines in same file → should be deduplicated to 1 entry
        lines = "\n".join(f"let m{i}: HashMap<u32, u32> = HashMap::new();" for i in range(5))
        (tmp_path / "lib.rs").write_text(lines)
        result = perf_suggest(tmp_path)
        hash_hits = [s for s in result["suggestions"] if s["rule_id"] == "PERF-MEM-003"]
        assert len(hash_hits) == 1

    def test_returns_summary_structure(self, tmp_path: Path):
        result = perf_suggest(tmp_path)
        assert "suggestions" in result
        assert "summary" in result
        assert "by_category" in result["summary"]
        assert "by_effort" in result["summary"]

    def test_empty_directory(self, tmp_path: Path):
        result = perf_suggest(tmp_path)
        assert result["summary"]["total_suggestions"] == 0

    def test_error_when_rules_missing(self, tmp_path: Path):
        from unittest.mock import patch
        with patch("src.tools.performance.Path.read_text", side_effect=OSError):
            result = perf_suggest(tmp_path)
        assert "error" in result


# ── rust_unsafe_audit ─────────────────────────────────────────────────────────

class TestRustUnsafeAudit:
    def test_detects_unsafe_block(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text(textwrap.dedent("""\
            fn risky() {
                unsafe {
                    *ptr = 42;
                }
            }
        """))
        result = rust_unsafe_audit(tmp_path)
        assert result["summary"]["total_unsafe"] >= 1
        assert result["unsafe_blocks"][0]["file"].endswith("lib.rs")

    def test_detects_safety_comment(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text(textwrap.dedent("""\
            fn ok() {
                // SAFETY: ptr is valid and aligned
                unsafe { *ptr = 1; }
            }
        """))
        result = rust_unsafe_audit(tmp_path)
        assert result["summary"]["total_unsafe"] >= 1
        assert result["summary"]["with_safety_comment"] >= 1

    def test_flags_missing_safety_comment(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text("fn bad() { unsafe { *p = 0; } }\n")
        result = rust_unsafe_audit(tmp_path)
        assert result["summary"]["without_safety_comment"] >= 1

    def test_detects_extern_c(self, tmp_path: Path):
        (tmp_path / "ffi.rs").write_text('extern "C" {\n    fn some_c_func(x: i32) -> i32;\n}\n')
        result = rust_unsafe_audit(tmp_path)
        assert result["summary"]["ffi_boundaries"] >= 1
        assert any(b["type"] == "extern_c" for b in result["ffi_boundaries"])

    def test_detects_raw_pointers(self, tmp_path: Path):
        (tmp_path / "lib.rs").write_text("fn raw_ptr(p: *mut u8) { unsafe { *p = 1; } }\n")
        result = rust_unsafe_audit(tmp_path)
        assert result["summary"]["raw_pointers"] >= 1

    def test_empty_project(self, tmp_path: Path):
        result = rust_unsafe_audit(tmp_path)
        assert result["summary"]["total_unsafe"] == 0
        assert result["summary"]["ffi_boundaries"] == 0

    def test_returns_all_sections(self, tmp_path: Path):
        result = rust_unsafe_audit(tmp_path)
        assert "unsafe_blocks" in result
        assert "ffi_boundaries" in result
        assert "raw_pointers" in result
        assert "summary" in result


# ── migration_validate ────────────────────────────────────────────────────────

class TestMigrationValidate:
    def _make_dump(self, tick: int, entities: list[dict]) -> dict:
        return {"tick": tick, "entities": entities}

    def test_passes_on_identical_dumps(self):
        entities = [{"id": 1, "health": 0.9, "age": 10}, {"id": 2, "health": 0.5, "age": 5}]
        before = self._make_dump(100, entities)
        after = self._make_dump(100, entities)
        result = migration_validate(before, after)
        assert result["passed"] is True
        assert result["diff_count"] == 0

    def test_detects_numeric_diff(self):
        before = self._make_dump(100, [{"id": 1, "health": 0.9}])
        after = self._make_dump(100, [{"id": 1, "health": 0.8}])
        result = migration_validate(before, after)
        assert result["passed"] is False
        assert result["diff_count"] >= 1
        assert result["diffs"][0]["field"] == "health"

    def test_tolerance_accepts_tiny_diff(self):
        before = self._make_dump(100, [{"id": 1, "value": 1.0}])
        after = self._make_dump(100, [{"id": 1, "value": 1.0 + 1e-9}])
        result = migration_validate(before, after, tolerance=1e-6)
        assert result["passed"] is True

    def test_tolerance_rejects_large_diff(self):
        before = self._make_dump(100, [{"id": 1, "value": 1.0}])
        after = self._make_dump(100, [{"id": 1, "value": 1.01}])
        result = migration_validate(before, after, tolerance=1e-6)
        assert result["passed"] is False

    def test_detects_missing_entity(self):
        before = self._make_dump(100, [{"id": 1}, {"id": 2}])
        after = self._make_dump(100, [{"id": 1}])
        result = migration_validate(before, after)
        assert result["passed"] is False
        assert 2 in result["missing_in_after"]

    def test_detects_extra_entity(self):
        before = self._make_dump(100, [{"id": 1}])
        after = self._make_dump(100, [{"id": 1}, {"id": 99}])
        result = migration_validate(before, after)
        assert result["passed"] is False
        assert 99 in result["extra_in_after"]

    def test_empty_dumps_pass(self):
        result = migration_validate({}, {})
        assert result["passed"] is True

    def test_reports_tick_values(self):
        before = self._make_dump(50, [])
        after = self._make_dump(50, [])
        result = migration_validate(before, after)
        assert result["before_tick"] == 50
        assert result["after_tick"] == 50
