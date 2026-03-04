"""Domain 3: Project Structure tools — project_overview, ffi_boundary_check (Phase 2)."""
import json
import re
import subprocess
from pathlib import Path

from .analysis import _safe_read


def project_overview(root: Path) -> dict:
    """Full project scan: Rust workspace, Godot structure, gdext bridge classes."""
    result: dict = {
        "rust_workspace": _scan_rust(root),
        "godot_project": _scan_godot(root),
        "bridge": _scan_bridge(root),
        "health": {},
    }

    # Health checks
    gp = result["godot_project"]
    rw = result["rust_workspace"]
    result["health"] = {
        "has_gdextension": gp.get("gdextension_file") is not None,
        "has_cargo_workspace": rw.get("is_workspace", False),
        "godot_project_found": gp.get("path") is not None,
        "rust_crates_found": len(rw.get("crates", [])) > 0,
        "bridge_classes_found": len(result["bridge"].get("gdextension_classes", [])) > 0,
        "missing_configs": _missing_configs(root, gp, rw),
    }
    return result


def _scan_rust(root: Path) -> dict:
    """Scan Rust workspace using cargo metadata."""
    meta_out = subprocess.run(
        ["cargo", "metadata", "--format-version=1"],
        capture_output=True, text=True, cwd=str(root), timeout=60,
    )
    if meta_out.returncode != 0:
        return {"error": meta_out.stderr[:300], "crates": [], "is_workspace": False}

    try:
        meta = json.loads(meta_out.stdout)
    except json.JSONDecodeError:
        return {"error": "Failed to parse cargo metadata", "crates": [], "is_workspace": False}

    workspace_members = set(meta.get("workspace_members", []))
    packages = meta.get("packages", [])

    crates = []
    total_lines = 0
    for pkg in packages:
        if pkg["id"] not in workspace_members and workspace_members:
            continue
        manifest = Path(pkg["manifest_path"])
        pkg_root = manifest.parent
        rs_files = list(pkg_root.rglob("*.rs"))
        lines = sum(_count_lines(f) for f in rs_files)
        total_lines += lines

        # Determine crate type from targets
        crate_types = []
        for t in pkg.get("targets", []):
            crate_types.extend(t.get("crate_types", []))

        crates.append({
            "name": pkg["name"],
            "version": pkg["version"],
            "path": _rel(manifest.parent, root),
            "type": list(set(crate_types)),
            "rs_files": len(rs_files),
            "lines": lines,
            "dependencies": [d["name"] for d in pkg.get("dependencies", []) if not d.get("optional", False)],
        })

    return {
        "is_workspace": bool(workspace_members),
        "crates": crates,
        "total_lines": total_lines,
        "total_files": sum(c["rs_files"] for c in crates),
    }


def _scan_godot(root: Path) -> dict:
    """Scan Godot project structure."""
    # Find project.godot
    project_godot = None
    for candidate in [root / "godot" / "project.godot", root / "project.godot"]:
        if candidate.exists():
            project_godot = candidate
            break

    if project_godot is None:
        # Try deeper search
        found = list(root.rglob("project.godot"))
        if found:
            project_godot = found[0]

    if project_godot is None:
        return {"path": None, "note": "No project.godot found"}

    godot_root = project_godot.parent
    result: dict = {"path": _rel(godot_root, root)}

    # Find .gdextension file
    gdext_files = list(godot_root.rglob("*.gdextension"))
    result["gdextension_file"] = _rel(gdext_files[0], root) if gdext_files else None

    # Scan autoloads from project.godot
    project_content = _safe_read(project_godot)
    autoloads = []
    in_autoload = False
    for line in project_content.splitlines():
        if line.strip() == "[autoload]":
            in_autoload = True
        elif line.startswith("[") and in_autoload:
            in_autoload = False
        elif in_autoload and "=" in line:
            name, path = line.split("=", 1)
            autoloads.append({"name": name.strip(), "script_path": path.strip().strip('"*')})
    result["autoloads"] = autoloads

    # Count GDScript files
    gd_files = list(godot_root.rglob("*.gd"))
    result["gdscript_files"] = [
        {
            "path": _rel(f, root),
            "lines": _count_lines(f),
        }
        for f in gd_files[:50]  # cap at 50
    ]
    result["gdscript_file_count"] = len(gd_files)

    # Count scenes
    result["scene_count"] = len(list(godot_root.rglob("*.tscn")))

    return result


def _scan_bridge(root: Path) -> dict:
    """Scan Rust↔Godot bridge: GodotClass structs, #[func], #[signal]."""
    rs_files = list(root.rglob("*.rs"))

    gdextension_classes = []
    exported_methods: list[dict] = []
    exported_signals: list[dict] = []

    for f in rs_files:
        content = _safe_read(f)
        if "#[derive(GodotClass)]" not in content:
            continue

        # Extract struct name and base class
        struct_matches = re.finditer(
            r"#\[class\(base=(\w+)\)\]\s*(?:#\[.*?\]\s*)*struct\s+(\w+)",
            content, re.DOTALL
        )
        for m in struct_matches:
            base_class = m.group(1)
            struct_name = m.group(2)
            rel_path = _rel(f, root)
            gdextension_classes.append({
                "rust_file": rel_path,
                "struct_name": struct_name,
                "base_class": base_class,
            })

        # Extract #[func] methods
        func_matches = re.finditer(
            r"#\[func\]\s*(?:pub\s+)?fn\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([^{]+?))?(?:\s*\{)",
            content
        )
        for m in func_matches:
            method_name = m.group(1)
            params = m.group(2).strip()
            return_type = m.group(3).strip() if m.group(3) else "void"
            exported_methods.append({
                "file": _rel(f, root),
                "method": method_name,
                "params": params,
                "return_type": return_type,
            })

        # Extract #[signal] declarations
        signal_matches = re.finditer(r"#\[signal\]\s*fn\s+(\w+)\s*\(([^)]*)\)", content)
        for m in signal_matches:
            exported_signals.append({
                "file": _rel(f, root),
                "signal": m.group(1),
                "params": m.group(2).strip(),
            })

    return {
        "gdextension_classes": gdextension_classes,
        "exported_methods": exported_methods[:50],
        "exported_signals": exported_signals,
    }


def _rel(path: Path, root: Path) -> str:
    """Return path relative to root, or absolute string if outside root."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _missing_configs(root: Path, gp: dict, rw: dict) -> list[str]:
    missing = []
    if not (root / "Cargo.toml").exists():
        missing.append("Cargo.toml")
    if gp.get("path") is None:
        missing.append("project.godot")
    if not gp.get("gdextension_file"):
        missing.append(".gdextension file")
    if not (root / ".mcp.json").exists() and not (root / "mcp.json").exists():
        missing.append(".mcp.json (MCP server registration)")
    return missing


def _count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0
