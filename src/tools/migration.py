"""Domain 4: Migration tools — migration_scan, migration_diff."""
import json
import re
from pathlib import Path

from .analysis import _safe_read


def migration_scan(root: Path, path: str = "", mode: str = "scan") -> dict:
    """Analyze GDScript files and estimate migration effort to Rust."""
    rules_file = Path(__file__).resolve().parent.parent / "rules" / "migration_map.json"
    try:
        migration_map = json.loads(rules_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"error": "Failed to load migration_map.json"}

    target = (root / path).resolve() if path else root

    if mode == "detail" and path and target.suffix == ".gd":
        return _scan_detail(target, root, migration_map)

    # Scan mode: summarize all .gd files
    gd_files = list(target.rglob("*.gd")) if target.is_dir() else ([target] if target.suffix == ".gd" else [])
    categories = migration_map.get("migration_categories", {})

    files_info = []
    for f in gd_files:
        content = _safe_read(f)
        category = _classify_file(content, categories)
        complexity = _measure_complexity(content)
        effort = _estimate_effort(complexity, content)
        cat_info = categories.get(category, {})
        files_info.append({
            "path": _rel_path(f, root),
            "lines": content.count("\n") + 1,
            "complexity": complexity,
            "migration_effort": effort,
            "category": category,
            "should_migrate": cat_info.get("should_migrate", True),
            "reason": cat_info.get("reason", ""),
        })

    should_migrate = [f for f in files_info if f["should_migrate"]]
    keep_gdscript = [f for f in files_info if not f["should_migrate"]]

    recommended_order = sorted(
        should_migrate,
        key=lambda f: {"trivial": 0, "moderate": 1, "complex": 2}[f["migration_effort"]]
    )

    return {
        "files": files_info,
        "summary": {
            "total_files": len(files_info),
            "total_lines": sum(f["lines"] for f in files_info),
            "should_migrate": len(should_migrate),
            "should_keep_gdscript": len(keep_gdscript),
            "estimated_rust_lines": sum(f["lines"] * 2 for f in should_migrate),
            "recommended_order": [f["path"] for f in recommended_order[:10]],
        },
    }


def migration_diff(root: Path, gdscript_path: str, rust_path: str) -> dict:
    """Compare GDScript source with converted Rust file for coverage gaps."""
    rules_file = Path(__file__).resolve().parent.parent / "rules" / "migration_map.json"
    try:
        migration_map = json.loads(rules_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        migration_map = {}

    gd_file = root / gdscript_path
    rs_file = root / rust_path

    if not gd_file.exists():
        return {"error": f"GDScript file not found: {gdscript_path}"}
    if not rs_file.exists():
        return {"error": f"Rust file not found: {rust_path}"}

    gd_content = _safe_read(gd_file)
    rs_content = _safe_read(rs_file)

    gd_methods = _extract_gd_methods(gd_content)
    rs_methods = _extract_rs_methods(rs_content)

    matched = [m for m in gd_methods if _rust_equivalent(m) in rs_methods or m in rs_methods]
    missing = [m for m in gd_methods if m not in matched]
    extra = [m for m in rs_methods if m not in gd_methods and _gd_equivalent(m) not in gd_methods]

    # Check function map patterns
    func_map = migration_map.get("function_map", {})
    pattern_checks = []
    for gd_pat, rs_pat in list(func_map.items())[:20]:
        gd_found = gd_pat.split("(")[0] in gd_content
        rs_found = rs_pat.split("(")[0].replace("rng.", "").replace("x.", "") in rs_content
        pattern_checks.append({
            "gdscript_pattern": gd_pat,
            "expected_rust_pattern": rs_pat,
            "found_in_gdscript": gd_found,
            "found_in_rust": rs_found if gd_found else None,
        })

    warnings = []
    if missing:
        warnings.append(f"{len(missing)} GDScript method(s) not found in Rust: {', '.join(missing[:5])}")
    if extra:
        warnings.append(f"{len(extra)} Rust method(s) have no GDScript counterpart (may be new): {', '.join(extra[:5])}")

    return {
        "coverage": {
            "gdscript_methods": len(gd_methods),
            "rust_methods": len(rs_methods),
            "matched": len(matched),
            "missing_in_rust": missing,
            "extra_in_rust": extra,
        },
        "pattern_checks": [p for p in pattern_checks if p["found_in_gdscript"]],
        "warnings": warnings,
    }


# ── Detail scan ──────────────────────────────────────────────────────────────

def _scan_detail(f: Path, root: Path, migration_map: dict) -> dict:
    content = _safe_read(f)
    func_map = migration_map.get("function_map", {})
    pattern_map = migration_map.get("pattern_map", {})
    type_map = migration_map.get("type_map", {})

    methods = _extract_gd_methods(content)
    signals = re.findall(r"^signal\s+(\w+)", content, re.MULTILINE)
    variables = re.findall(r"^(?:var|const|export var)\s+(\w+)(?:\s*:\s*(\w+))?", content, re.MULTILINE)

    # Find used GDScript functions that have Rust equivalents
    migration_notes = []
    for gd_fn, rs_fn in func_map.items():
        fn_name = gd_fn.split("(")[0]
        if fn_name in content:
            migration_notes.append(f"{gd_fn}  →  {rs_fn}")

    for gd_pat, rs_pat in pattern_map.items():
        gd_key = gd_pat.split("(")[0].split(" ")[0]
        if gd_key in content:
            migration_notes.append(f"{gd_pat}  →  {rs_pat}")

    # Risk factors
    risk_factors = []
    if content.count("Dictionary") > 3:
        risk_factors.append("Heavy Dictionary use — will need HashMap or struct in Rust")
    if "yield(" in content:
        risk_factors.append("yield() coroutines — replace with state machine or async pattern")
    if "get_tree()" in content:
        risk_factors.append("get_tree() access — not available in pure Rust, use event system")
    if re.search(r"\bDynamic\b|\bVariant\b", content):
        risk_factors.append("Dynamic typing — Rust will require explicit enum or trait objects")

    # Generate Rust skeleton
    skeleton = _generate_rust_skeleton(f.stem, methods, signals, variables, type_map)

    return {
        "gdscript_analysis": {
            "methods": methods,
            "signals": signals,
            "variables": [{"name": v[0], "type": v[1] or "Variant"} for v in variables],
        },
        "rust_skeleton": skeleton,
        "migration_notes": migration_notes[:20],
        "risk_factors": risk_factors,
        "complexity": _measure_complexity(content),
        "migration_effort": _estimate_effort(_measure_complexity(content), content),
    }


def _generate_rust_skeleton(
    class_name: str,
    methods: list[str],
    signals: list[str],
    variables: list[tuple],
    type_map: dict,
) -> str:
    pascal = _to_pascal(class_name)
    fields = "\n".join(
        f"    pub {v[0]}: {type_map.get(v[1], 'f64') if v[1] else 'f64'},"
        for v in variables[:10]
    )
    method_stubs = "\n\n".join(
        f"    #[func]\n    pub fn {m}(&mut self) {{\n        todo!()\n    }}"
        for m in methods[:10]
    )
    signal_defs = "\n".join(
        f"    #[signal]\n    fn {s}();" for s in signals[:5]
    )

    return f"""\
use godot::prelude::*;

#[derive(GodotClass)]
#[class(base=Node)]
pub struct {pascal} {{
    base: Base<Node>,
{fields}
}}

#[godot_api]
impl INode for {pascal} {{
    fn init(base: Base<Node>) -> Self {{
        Self {{
            base,
            // TODO: initialize fields
        }}
    }}
}}

#[godot_api]
impl {pascal} {{
{signal_defs}

{method_stubs}
}}
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _classify_file(content: str, categories: dict) -> str:
    for cat_name, cat in categories.items():
        for pat in cat.get("patterns", []):
            if pat in content:
                return cat_name
    return "logic"


def _measure_complexity(content: str) -> str:
    func_count = len(re.findall(r"^func\s+\w+", content, re.MULTILINE))
    line_count = content.count("\n")
    dynamic_count = content.count("Dictionary") + content.count("Array") + content.count("Variant")
    score = func_count + (line_count // 50) + dynamic_count
    if score < 5:
        return "low"
    if score < 15:
        return "medium"
    return "high"


def _estimate_effort(complexity: str, content: str) -> str:
    if complexity == "low" and "yield" not in content and "get_tree" not in content:
        return "trivial"
    if complexity == "high" or "yield(" in content or content.count("Dictionary") > 5:
        return "complex"
    return "moderate"


def _extract_gd_methods(content: str) -> list[str]:
    return re.findall(r"^func\s+(\w+)\s*\(", content, re.MULTILINE)


def _extract_rs_methods(content: str) -> list[str]:
    return re.findall(r"(?:pub\s+)?fn\s+(\w+)\s*\(", content)


def _rust_equivalent(gd_name: str) -> str:
    return gd_name  # GDScript uses snake_case, Rust too — same names


def _gd_equivalent(rs_name: str) -> str:
    return rs_name


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _to_pascal(name: str) -> str:
    return "".join(word.capitalize() for word in name.split("_"))
