"""Domain 5: Performance tools — perf_suggest, perf_profile (basic), rust_unsafe_audit."""
import json
import re
from pathlib import Path

from .analysis import _safe_read


def perf_suggest(root: Path, path: str = "", focus: str = "all") -> dict:
    """Scan Rust code for performance optimization opportunities using rule DB."""
    rules_file = Path(__file__).resolve().parent.parent / "rules" / "perf_rules.json"
    try:
        rules = json.loads(rules_file.read_text(encoding="utf-8"))["rules"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {"error": "Failed to load perf_rules.json"}

    # Filter by focus category
    if focus != "all":
        rules = [r for r in rules if r.get("category") == focus]

    target = (root / path).resolve() if path else root
    rs_files = list(target.rglob("*.rs")) if target.is_dir() else ([target] if target.suffix == ".rs" else [])

    suggestions: list[dict] = []

    for f in rs_files:
        content = _safe_read(f)
        if not content:
            continue
        for rule in rules:
            try:
                matches = list(re.finditer(rule["pattern"], content, re.DOTALL))
            except re.error:
                continue
            for m in matches:
                lineno = content[: m.start()].count("\n") + 1
                suggestions.append({
                    "file": _rel_path(f, root),
                    "line": lineno,
                    "rule_id": rule["id"],
                    "category": rule["category"],
                    "message": rule["message"],
                    "suggestion": rule["suggestion"],
                    "effort": rule["effort"],
                    "expected_improvement": rule["expected_improvement"],
                })

    # Deduplicate: one suggestion per (file, rule) to avoid flooding
    seen: set[tuple] = set()
    deduped = []
    for s in suggestions:
        key = (s["file"], s["rule_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    summary = {
        "total_suggestions": len(deduped),
        "by_category": {},
        "by_effort": {"trivial": 0, "moderate": 0, "significant": 0},
    }
    for s in deduped:
        cat = s["category"]
        summary["by_category"][cat] = summary["by_category"].get(cat, 0) + 1
        effort = s["effort"]
        if effort in summary["by_effort"]:
            summary["by_effort"][effort] += 1

    return {"suggestions": deduped[:50], "summary": summary}


def rust_unsafe_audit(root: Path, path: str = "") -> dict:
    """Audit all unsafe blocks and FFI boundaries in Rust code."""
    target = (root / path).resolve() if path else root
    rs_files = list(target.rglob("*.rs")) if target.is_dir() else ([target] if target.suffix == ".rs" else [])

    unsafe_blocks: list[dict] = []
    ffi_boundaries: list[dict] = []
    raw_pointers: list[dict] = []

    for f in rs_files:
        content = _safe_read(f)
        lines = content.splitlines()

        # Unsafe blocks
        for lineno, line in enumerate(lines, 1):
            if re.search(r"\bunsafe\s*\{", line) and not line.strip().startswith("//"):
                has_comment = _has_safety_comment(lines, lineno - 1)
                # Try to extract context (surrounding lines)
                ctx_start = max(0, lineno - 3)
                ctx = " | ".join(lines[ctx_start:lineno]).strip()[:120]
                unsafe_blocks.append({
                    "file": _rel_path(f, root),
                    "line": lineno,
                    "context": ctx,
                    "has_safety_comment": has_comment,
                    "reason": _guess_unsafe_reason(ctx),
                })

        # FFI boundaries: extern "C" functions and #[no_mangle]
        for lineno, line in enumerate(lines, 1):
            if re.search(r'extern\s+"C"', line) or "#[no_mangle]" in line:
                ffi_boundaries.append({
                    "file": _rel_path(f, root),
                    "line": lineno,
                    "type": "extern_c" if "extern" in line else "no_mangle",
                    "declaration": line.strip()[:100],
                })

        # Raw pointers
        for lineno, line in enumerate(lines, 1):
            raw_matches = re.findall(r"\*(?:const|mut)\s+\w+", line)
            for ptr_type in raw_matches:
                if not line.strip().startswith("//"):
                    raw_pointers.append({
                        "file": _rel_path(f, root),
                        "line": lineno,
                        "type": ptr_type,
                    })

    with_comments = sum(1 for b in unsafe_blocks if b["has_safety_comment"])
    without_comments = len(unsafe_blocks) - with_comments

    return {
        "unsafe_blocks": unsafe_blocks[:50],
        "ffi_boundaries": ffi_boundaries[:30],
        "raw_pointers": raw_pointers[:30],
        "summary": {
            "total_unsafe": len(unsafe_blocks),
            "with_safety_comment": with_comments,
            "without_safety_comment": without_comments,
            "ffi_boundaries": len(ffi_boundaries),
            "raw_pointers": len(raw_pointers),
        },
    }


def migration_validate(before_dump: dict, after_dump: dict, tolerance: float = 1e-6) -> dict:
    """Compare two golden dump snapshots (from godot_golden_dump) for parity."""
    before_entities = {e.get("id"): e for e in before_dump.get("entities", [])}
    after_entities = {e.get("id"): e for e in after_dump.get("entities", [])}

    diffs: list[dict] = []
    missing_in_after = [eid for eid in before_entities if eid not in after_entities]
    extra_in_after = [eid for eid in after_entities if eid not in before_entities]

    for eid in before_entities:
        if eid not in after_entities:
            continue
        before_e = before_entities[eid]
        after_e = after_entities[eid]
        for field in set(before_e) | set(after_e):
            bv = before_e.get(field)
            av = after_e.get(field)
            if bv != av:
                delta = None
                if isinstance(bv, (int, float)) and isinstance(av, (int, float)):
                    delta = abs(float(av) - float(bv))
                    if delta <= tolerance:
                        continue  # within tolerance
                diffs.append({
                    "entity_id": eid,
                    "field": field,
                    "before_value": bv,
                    "after_value": av,
                    "delta": delta,
                })

    passed = len(diffs) == 0 and not missing_in_after and not extra_in_after

    return {
        "passed": passed,
        "diff_count": len(diffs),
        "diffs": diffs[:20],
        "missing_in_after": missing_in_after[:10],
        "extra_in_after": extra_in_after[:10],
        "before_tick": before_dump.get("tick"),
        "after_tick": after_dump.get("tick"),
        "tolerance": tolerance,
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _has_safety_comment(lines: list[str], unsafe_lineno: int) -> bool:
    start = max(0, unsafe_lineno - 3)
    return any("SAFETY" in l or "Safety:" in l for l in lines[start:unsafe_lineno])


def _guess_unsafe_reason(context: str) -> str:
    ctx_lower = context.lower()
    if "extern" in ctx_lower or "ffi" in ctx_lower:
        return "FFI call"
    if "*mut" in context or "*const" in context or "ptr" in ctx_lower:
        return "Raw pointer dereference"
    if "transmute" in ctx_lower:
        return "Memory transmutation"
    if "slice" in ctx_lower or "from_raw_parts" in ctx_lower:
        return "Slice from raw parts"
    return "Unknown — add SAFETY comment"


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
