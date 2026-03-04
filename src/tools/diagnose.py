"""Domain 7: Debug & Diagnose tools — diagnose, build_explain."""
import json
import re
import subprocess
from pathlib import Path


def diagnose(error: str, context: str = "auto") -> dict:
    """Match error string against known pattern DB, return root cause + solutions."""
    patterns_file = Path(__file__).resolve().parent.parent / "rules" / "error_patterns.json"
    try:
        patterns = json.loads(patterns_file.read_text(encoding="utf-8"))["patterns"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {"error": "Failed to load error_patterns.json"}

    # Auto-detect context
    if context == "auto":
        context = _detect_context(error)

    matches = []
    for p in patterns:
        if p.get("context") not in (context, "build", "runtime", "godot") and context != "auto":
            if p.get("context") != context:
                continue
        try:
            if re.search(p["match"], error, re.IGNORECASE | re.DOTALL):
                matches.append(p)
        except re.error:
            if p["match"].lower() in error.lower():
                matches.append(p)

    if not matches:
        return {
            "error_type": "unknown",
            "context": context,
            "root_cause": "No matching pattern found in error DB",
            "solutions": [
                {
                    "description": "Search the godot-rust/gdext GitHub issues for this error",
                    "code_change": "",
                    "confidence": "medium",
                }
            ],
            "raw_error": error[:500],
        }

    best = matches[0]
    return {
        "error_type": best.get("error_type", "unknown"),
        "pattern_id": best.get("id", ""),
        "context": context,
        "root_cause": best.get("root_cause", ""),
        "solutions": best.get("solutions", []),
        "all_matches": len(matches),
    }


def build_explain(root: Path, package: str = "") -> dict:
    """Run cargo build and explain errors in plain language."""
    args = ["cargo", "build", "--message-format=json"]
    if package:
        args += ["-p", package]

    try:
        result = subprocess.run(
            args, capture_output=True, text=True, cwd=str(root), timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "errors": [], "error": "cargo build timed out after 300s"}
    except FileNotFoundError:
        return {"success": False, "errors": [], "error": "cargo not found in PATH"}

    success = result.returncode == 0
    errors: list[dict] = []
    warnings: list[dict] = []

    for line in result.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") != "compiler-message":
            continue
        inner = msg.get("message", {})
        level = inner.get("level", "")
        if level not in ("error", "warning"):
            continue

        text = inner.get("message", "")
        code_obj = inner.get("code") or {}
        error_code = code_obj.get("code", "") if code_obj else ""
        spans = inner.get("spans", [])
        span = spans[0] if spans else {}

        entry = {
            "raw": text,
            "error_code": error_code,
            "file": span.get("file_name", ""),
            "line": span.get("line_start", 0),
            "explanation": _explain_error(error_code, text),
            "fix_suggestion": _suggest_fix(error_code, text),
        }

        if level == "error":
            errors.append(entry)
        else:
            warnings.append({"raw": text, "file": span.get("file_name", ""), "line": span.get("line_start", 0)})

    return {
        "success": success,
        "errors": errors[:20],
        "warnings": warnings[:20],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


# ── Error explanation DB ────────────────────────────────────────────────────

_ERROR_EXPLANATIONS: dict[str, str] = {
    "E0308": "Type mismatch — the function or binding expects a different type than what was provided.",
    "E0382": "Value used after being moved — once moved into another variable or function, the original is invalid.",
    "E0502": "Borrow conflict — you can't have a mutable borrow while an immutable borrow is active.",
    "E0499": "Multiple mutable borrows — Rust allows only one mutable borrow at a time.",
    "E0505": "Borrow outlives its source — the reference would outlive the value it borrows.",
    "E0507": "Cannot move out of borrowed content — you can't take ownership from behind a reference.",
    "E0515": "Returned value references local data — the referenced value goes out of scope on return.",
    "E0597": "Value does not live long enough — a reference outlives its source data.",
    "E0277": "Trait not implemented — the type doesn't implement a required trait.",
    "E0432": "Unresolved import — the module path doesn't exist or isn't imported.",
    "E0433": "Failed to resolve — name not found in scope.",
    "E0583": "File not found for module — the module file doesn't exist at the expected path.",
    "E0601": "No main function — binary crates need a main() function.",
    "E0658": "Feature not enabled — this feature requires a feature flag or nightly Rust.",
}

_FIX_SUGGESTIONS: dict[str, str] = {
    "E0308": "Check the expected type in the function signature. Use .into() for compatible conversions.",
    "E0382": "Clone the value before the move if you need it later: let copy = value.clone();",
    "E0502": "Restructure to drop the immutable borrow before taking a mutable one.",
    "E0499": "Use a single mutable borrow or restructure into separate scopes.",
    "E0507": "Clone the inner value: field.clone(), or use a reference &field.",
    "E0515": "Return an owned value instead of a reference to local data.",
    "E0597": "Ensure the referenced value lives at least as long as the reference.",
    "E0277": "Implement the required trait or use a type that already implements it.",
    "E0432": "Add 'use crate::module::Type;' or check the module path is correct.",
    "E0433": "Check spelling. Add 'use' import for the missing name.",
}


def _explain_error(code: str, message: str) -> str:
    if code in _ERROR_EXPLANATIONS:
        return _ERROR_EXPLANATIONS[code]
    # Fallback: clean up the raw message
    return message[:200] if message else "See Rust error docs: https://doc.rust-lang.org/error_codes/"


def _suggest_fix(code: str, message: str) -> str:
    if code in _FIX_SUGGESTIONS:
        return _FIX_SUGGESTIONS[code]
    return ""


def _detect_context(error: str) -> str:
    error_lower = error.lower()
    if any(k in error_lower for k in ["error[e", "cargo", "compiling", "linker"]):
        return "build"
    if any(k in error_lower for k in ["gdextension", "can't load", "script inherits"]):
        return "godot"
    if any(k in error_lower for k in ["panic", "thread", "runtime", "borrow"]):
        return "runtime"
    return "build"
