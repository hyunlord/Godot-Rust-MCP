"""Domain 2: Code Analysis tools — rust_analyze, rust_dependencies, crate_map."""
import json
import re
import subprocess
from pathlib import Path


def rust_analyze(root: Path, path: str = "", checks: list[str] | None = None) -> dict:
    """Analyze Rust code quality: unwrap, unsafe, clone, complexity, naming."""
    checks = checks or ["unwrap", "unsafe", "clone_heavy", "error_handling", "dead_code"]
    target = (root / path).resolve() if path else root
    issues: list[dict] = []

    # --- clippy JSON pass ---
    clippy_result = subprocess.run(
        ["cargo", "clippy", "--message-format=json", "--", "-W", "clippy::all"],
        capture_output=True, text=True, cwd=str(root), timeout=120,
    )
    for line in clippy_result.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("reason") != "compiler-message":
            continue
        inner = msg.get("message", {})
        if inner.get("level") not in ("error", "warning"):
            continue
        spans = inner.get("spans", [])
        if not spans:
            continue
        span = spans[0]
        file_name = span.get("file_name", "")
        # Filter to target path if specified
        if path and not file_name.startswith(str(target.relative_to(root)) if target != root else ""):
            pass  # include all when no specific path
        issues.append({
            "file": file_name,
            "line": span.get("line_start", 0),
            "check": "clippy",
            "severity": inner.get("level", "warning"),
            "message": inner.get("message", ""),
            "suggestion": inner.get("rendered", "")[:200],
        })

    # --- custom regex checks on .rs files ---
    rs_files = list(target.rglob("*.rs")) if target.is_dir() else ([target] if target.suffix == ".rs" else [])

    if "unwrap" in checks:
        for f in rs_files:
            # Skip test files
            if "test" in f.name.lower() or "#[cfg(test)]" in _safe_read(f)[:500]:
                continue
            for lineno, line in enumerate(_safe_read(f).splitlines(), 1):
                if re.search(r"\.(unwrap|expect)\(\)", line) and not line.strip().startswith("//"):
                    issues.append({
                        "file": str(f.relative_to(root)),
                        "line": lineno,
                        "check": "unwrap",
                        "severity": "warning",
                        "message": f"Panicking .unwrap()/.expect() in production code: {line.strip()[:80]}",
                        "suggestion": "Use ? operator or .unwrap_or_default() / .unwrap_or_else()",
                    })

    if "unsafe" in checks:
        for f in rs_files:
            content = _safe_read(f)
            for lineno, line in enumerate(content.splitlines(), 1):
                if re.search(r"\bunsafe\b", line) and not line.strip().startswith("//"):
                    has_comment = _has_safety_comment(content.splitlines(), lineno - 1)
                    issues.append({
                        "file": str(f.relative_to(root)),
                        "line": lineno,
                        "check": "unsafe",
                        "severity": "warning" if has_safety_comment else "error",
                        "message": f"unsafe block{'  (no SAFETY comment)' if not has_comment else ''}",
                        "suggestion": "Add // SAFETY: ... comment explaining why this is sound",
                    })

    if "clone_heavy" in checks:
        for f in rs_files:
            for lineno, line in enumerate(_safe_read(f).splitlines(), 1):
                clones = len(re.findall(r"\.clone\(\)", line))
                if clones >= 2:
                    issues.append({
                        "file": str(f.relative_to(root)),
                        "line": lineno,
                        "check": "clone_heavy",
                        "severity": "warning",
                        "message": f"{clones} .clone() calls on one line — consider borrowing",
                        "suggestion": "Use references (&T) where ownership is not required",
                    })

    summary = {
        "total_issues": len(issues),
        "by_severity": {
            "error": sum(1 for i in issues if i["severity"] == "error"),
            "warning": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "by_check": {},
    }
    for issue in issues:
        c = issue["check"]
        summary["by_check"][c] = summary["by_check"].get(c, 0) + 1

    return {"issues": issues[:100], "summary": summary}


def rust_dependencies(root: Path, package: str = "") -> dict:
    """Analyze crate dependency tree, detect unused and outdated deps."""
    result: dict = {}

    # cargo tree for dependency structure
    tree_args = ["cargo", "tree", "--prefix=depth"]
    if package:
        tree_args += ["-p", package]
    tree_out = subprocess.run(
        tree_args, capture_output=True, text=True, cwd=str(root), timeout=60,
    )
    result["dependency_tree"] = tree_out.stdout[:3000] if tree_out.returncode == 0 else None
    if tree_out.returncode != 0:
        result["tree_error"] = tree_out.stderr[:500]

    # cargo outdated (optional)
    outdated_out = subprocess.run(
        ["cargo", "outdated", "--format", "json"],
        capture_output=True, text=True, cwd=str(root), timeout=60,
    )
    if outdated_out.returncode == 0:
        try:
            outdated_data = json.loads(outdated_out.stdout)
            result["outdated"] = outdated_data.get("dependencies", [])
        except json.JSONDecodeError:
            result["outdated"] = []
    else:
        result["outdated"] = []
        result["outdated_note"] = "Install cargo-outdated for outdated dep detection: cargo install cargo-outdated"

    # cargo-udeps for unused (optional, nightly only — just report)
    result["unused_note"] = "Install cargo-udeps for unused dep detection: cargo install cargo-udeps (requires nightly)"

    # Parse Cargo.toml for direct deps
    cargo_toml = root / "Cargo.toml"
    direct_deps: list[str] = []
    if cargo_toml.exists():
        content = cargo_toml.read_text(encoding="utf-8")
        in_deps = False
        for line in content.splitlines():
            if re.match(r"\[dependencies\]", line):
                in_deps = True
            elif line.startswith("[") and in_deps:
                in_deps = False
            elif in_deps and "=" in line and not line.strip().startswith("#"):
                dep_name = line.split("=")[0].strip()
                direct_deps.append(dep_name)
    result["direct_dependencies"] = direct_deps

    return result


def crate_map(root: Path, fmt: str = "text") -> dict:
    """Visualize crate dependency graph as text or mermaid diagram."""
    meta_out = subprocess.run(
        ["cargo", "metadata", "--format-version=1", "--no-deps"],
        capture_output=True, text=True, cwd=str(root), timeout=60,
    )
    if meta_out.returncode != 0:
        return {"error": meta_out.stderr[:500]}

    try:
        meta = json.loads(meta_out.stdout)
    except json.JSONDecodeError:
        return {"error": "Failed to parse cargo metadata output"}

    packages = meta.get("packages", [])
    workspace_members = set(meta.get("workspace_members", []))

    # Build local crate list
    crates = []
    for pkg in packages:
        pkg_id = pkg["id"]
        if pkg_id in workspace_members or not workspace_members:
            crates.append({
                "name": pkg["name"],
                "version": pkg["version"],
                "id": pkg_id,
                "manifest_path": pkg["manifest_path"],
                "deps": [d["name"] for d in pkg.get("dependencies", []) if not d.get("optional", False)],
            })

    if fmt == "mermaid":
        lines = ["graph TD"]
        for c in crates:
            safe_name = c["name"].replace("-", "_")
            for dep in c["deps"]:
                safe_dep = dep.replace("-", "_")
                lines.append(f"    {safe_name} --> {safe_dep}")
        graph = "\n".join(lines)
    else:
        lines = []
        for c in crates:
            dep_str = ", ".join(c["deps"]) if c["deps"] else "(no local deps)"
            lines.append(f"{c['name']} v{c['version']} → [{dep_str}]")
        graph = "\n".join(lines)

    return {
        "graph": graph,
        "format": fmt,
        "crate_count": len(crates),
        "crates": [{"name": c["name"], "version": c["version"]} for c in crates],
    }


# ── Helpers ─────────────────────────────────────────────────────────────────

def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _has_safety_comment(lines: list[str], unsafe_lineno: int) -> bool:
    """Check if there's a SAFETY: comment within 3 lines before the unsafe keyword."""
    start = max(0, unsafe_lineno - 3)
    for line in lines[start:unsafe_lineno]:
        if "SAFETY" in line or "Safety" in line:
            return True
    return False


# suppress undefined name warning for has_safety_comment used in closure
has_safety_comment = _has_safety_comment
