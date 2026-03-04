"""Domain 6: gdext Patterns — gdext_check, gdext_scaffold, gdext_version_check."""
import json
import re
import subprocess
from pathlib import Path

from .analysis import _safe_read


def gdext_check(root: Path, path: str = "") -> dict:
    """Check Rust source for gdext anti-patterns using rule DB."""
    rules_file = Path(__file__).resolve().parent.parent / "rules" / "gdext_rules.json"
    try:
        rules = json.loads(rules_file.read_text(encoding="utf-8"))["rules"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {"error": "Failed to load gdext_rules.json"}

    target = (root / path).resolve() if path else root
    rs_files = list(target.rglob("*.rs")) if target.is_dir() else ([target] if target.suffix == ".rs" else [])

    issues: list[dict] = []

    for f in rs_files:
        content = _safe_read(f)
        # Only check files that use gdext
        if not any(kw in content for kw in ["GodotClass", "#[func]", "#[var]", "#[export]", "godot::prelude"]):
            continue

        for rule in rules:
            try:
                matches = list(re.finditer(rule["pattern"], content, re.DOTALL))
            except re.error:
                continue
            for m in matches:
                # Find line number from match start
                lineno = content[: m.start()].count("\n") + 1
                issues.append({
                    "file": _rel_path(f, root),
                    "line": lineno,
                    "rule_id": rule["id"],
                    "rule_name": rule["name"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "suggestion": rule["suggestion"],
                    "category": rule["category"],
                })

    summary = {
        "total_issues": len(issues),
        "by_severity": {
            "error": sum(1 for i in issues if i["severity"] == "error"),
            "warning": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "by_category": {},
        "rules_checked": len(rules),
    }
    for issue in issues:
        c = issue["category"]
        summary["by_category"][c] = summary["by_category"].get(c, 0) + 1

    return {"issues": issues[:50], "summary": summary}


def gdext_scaffold(
    name: str,
    pattern: str = "godot_class",
    base: str = "Node",
    fields: list[dict] | None = None,
) -> dict:
    """Generate boilerplate Rust code for common gdext patterns."""
    fields = fields or []
    generators = {
        "godot_class": _scaffold_godot_class,
        "singleton": _scaffold_singleton,
        "resource": _scaffold_resource,
        "bridge_class": _scaffold_bridge_class,
        "signal_hub": _scaffold_signal_hub,
        "export_enum": _scaffold_export_enum,
    }
    gen = generators.get(pattern)
    if gen is None:
        return {
            "error": f"Unknown pattern: {pattern!r}",
            "available": list(generators.keys()),
        }
    code, notes = gen(name, base, fields)
    snake = _to_snake(name)
    return {
        "code": code,
        "file_path": f"src/{snake}.rs",
        "pattern": pattern,
        "notes": notes,
        "usage_gdscript": f"var node = {name}.new()\nnode.your_method()",
    }


def gdext_version_check(root: Path) -> dict:
    """Check gdext version vs Godot binary version compatibility."""
    result: dict = {}

    # Read gdext version from Cargo.toml / Cargo.lock
    cargo_toml = root / "Cargo.toml"
    gdext_version = _find_gdext_version(root)
    result["gdext_version"] = gdext_version

    # Get api feature flag
    result["api_feature"] = _find_api_feature(root)

    # Get Godot binary version
    godot_bin = "godot"
    godot_version = _get_godot_version(godot_bin)
    result["godot_version"] = godot_version

    # Compatibility check
    warnings = _compatibility_warnings(gdext_version, godot_version, result.get("api_feature"))
    result["compatible"] = len([w for w in warnings if "crash" in w.lower() or "error" in w.lower()]) == 0
    result["warnings"] = warnings

    return result


# ── Scaffold generators ──────────────────────────────────────────────────────

def _scaffold_godot_class(name: str, base: str, fields: list[dict]) -> tuple[str, list[str]]:
    field_lines = _render_fields(fields)
    code = f"""\
use godot::prelude::*;

#[derive(GodotClass)]
#[class(base={base})]
pub struct {name} {{
    base: Base<{base}>,
{field_lines}\
}}

#[godot_api]
impl I{base} for {name} {{
    fn init(base: Base<{base}>) -> Self {{
        Self {{
            base,
{_render_field_defaults(fields)}\
        }}
    }}

    fn ready(&mut self) {{
    }}

    fn process(&mut self, _delta: f64) {{
    }}
}}

#[godot_api]
impl {name} {{
    // Add your #[func] methods here
}}
"""
    notes = [
        f"Place in src/{_to_snake(name)}.rs",
        "Register in your ExtensionLibrary: #[gdextension] impl ExtensionLibrary for MyLib {}",
        "Access from GDScript: var n = MyNode.new()",
    ]
    return code, notes


def _scaffold_singleton(name: str, base: str, fields: list[dict]) -> tuple[str, list[str]]:
    code = f"""\
use godot::prelude::*;

/// Autoload singleton — register in Project Settings > Autoload
#[derive(GodotClass)]
#[class(base=Node)]
pub struct {name} {{
    base: Base<Node>,
}}

#[godot_api]
impl INode for {name} {{
    fn init(base: Base<Node>) -> Self {{
        Self {{ base }}
    }}
}}

#[godot_api]
impl {name} {{
    /// Get the singleton from anywhere in Rust
    pub fn singleton(base: &mut Base<impl Inherits<Node>>) -> Gd<{name}> {{
        base.get_tree()
            .unwrap()
            .root()
            .unwrap()
            .get_node_as::<{name}>("{name}")
    }}

    #[func]
    pub fn example_method(&self) -> GString {{
        GString::from("hello from {name}")
    }}
}}
"""
    notes = [
        f"Register '{name}' as Autoload in Project Settings → Autoload",
        f"Path: res://addons/your_ext/{_to_snake(name)}.gdextension-class",
        "Access from GDScript: {name}.example_method()",
    ]
    return code, notes


def _scaffold_resource(name: str, base: str, fields: list[dict]) -> tuple[str, list[str]]:
    field_lines = _render_fields(fields, export=True)
    code = f"""\
use godot::prelude::*;

#[derive(GodotClass)]
#[class(base=Resource, init)]
pub struct {name} {{
    base: Base<Resource>,
{field_lines}\
}}

#[godot_api]
impl {name} {{
    // Add helper methods here
}}
"""
    notes = [
        "Custom Resources can be created and saved in the Godot editor",
        "Use #[export] fields to expose them to the editor inspector",
        "Load from GDScript: var res = load(\"res://data/my_config.tres\") as {name}",
    ]
    return code, notes


def _scaffold_bridge_class(name: str, base: str, fields: list[dict]) -> tuple[str, list[str]]:
    code = f"""\
use godot::prelude::*;

/// Bridge between Godot scene tree and Rust ECS/simulation.
/// Keep this class thin — delegate all logic to pure Rust types.
#[derive(GodotClass)]
#[class(base={base})]
pub struct {name} {{
    base: Base<{base}>,
    // Add your Rust simulation engine here:
    // engine: SimulationEngine,
}}

#[godot_api]
impl I{base} for {name} {{
    fn init(base: Base<{base}>) -> Self {{
        Self {{
            base,
            // engine: SimulationEngine::new(),
        }}
    }}

    fn ready(&mut self) {{
        godot_print!("[{name}] ready");
    }}
}}

#[godot_api]
impl {name} {{
    /// Advance simulation by n ticks. Called from GDScript or harness.
    #[func]
    pub fn tick(&mut self, n: i32) -> Dictionary {{
        // self.engine.tick(n as u32);
        let mut result = Dictionary::new();
        result.set("tick", n);
        result
    }}

    /// Get snapshot of current state for inspection.
    #[func]
    pub fn snapshot(&self) -> Dictionary {{
        let mut d = Dictionary::new();
        // d.set("entities", self.engine.alive_count() as i64);
        d
    }}
}}
"""
    notes = [
        "Keep this class thin — move simulation logic to pure Rust structs",
        "Use Dictionary for simple data, PackedByteArray for bulk transfers",
        "harness_server.gd will call tick() and snapshot() via WebSocket",
    ]
    return code, notes


def _scaffold_signal_hub(name: str, base: str, fields: list[dict]) -> tuple[str, list[str]]:
    code = f"""\
use godot::prelude::*;

/// Central signal hub — Autoload singleton for game-wide events.
#[derive(GodotClass)]
#[class(base=Node)]
pub struct {name} {{
    base: Base<Node>,
}}

#[godot_api]
impl INode for {name} {{
    fn init(base: Base<Node>) -> Self {{
        Self {{ base }}
    }}
}}

#[godot_api]
impl {name} {{
    /// Example signal — add more as needed
    #[signal]
    fn entity_died(entity_id: i64);

    #[signal]
    fn tick_completed(tick: i64, alive_count: i64);
}}
"""
    notes = [
        f"Register '{name}' as Autoload to make it globally accessible",
        "Emit from Rust: self.base_mut().emit_signal(\"entity_died\", &[id.to_variant()])",
        "Connect from GDScript: {name}.entity_died.connect(_on_entity_died)",
    ]
    return code, notes


def _scaffold_export_enum(name: str, base: str, fields: list[dict]) -> tuple[str, list[str]]:
    code = f"""\
use godot::prelude::*;

/// Enum exported to GDScript — use as property type in exported classes.
#[derive(GodotConvert, Var, Export, Debug, Clone, Copy, PartialEq)]
#[godot(via = GString)]
pub enum {name} {{
    VariantA,
    VariantB,
    VariantC,
}}

impl Default for {name} {{
    fn default() -> Self {{
        Self::VariantA
    }}
}}
"""
    notes = [
        "Use as a property type in GodotClass: #[export] my_field: {name}",
        "GDScript sees string values: \"VariantA\", \"VariantB\", etc.",
        "Consider #[godot(via = i64)] for int-based enums (more efficient)",
    ]
    return code, notes


# ── Helpers ──────────────────────────────────────────────────────────────────

def _render_fields(fields: list[dict], export: bool = False) -> str:
    if not fields:
        return ""
    lines = []
    for f in fields:
        name = f.get("name", "field")
        typ = f.get("type", "f64")
        prefix = "    #[export]\n    " if export or f.get("export") else "    "
        lines.append(f"{prefix}pub {name}: {typ},")
    return "\n".join(lines) + "\n"


def _render_field_defaults(fields: list[dict]) -> str:
    if not fields:
        return ""
    lines = []
    for f in fields:
        name = f.get("name", "field")
        default = f.get("default", "Default::default()")
        lines.append(f"            {name}: {default},")
    return "\n".join(lines) + "\n"


def _to_snake(name: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name)
    return s.lower()


def _rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _find_gdext_version(root: Path) -> str | None:
    # Check Cargo.lock first for exact version
    lock = root / "Cargo.lock"
    if lock.exists():
        content = lock.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'name = "godot"\nversion = "([^"]+)"', content)
        if m:
            return m.group(1)
    # Fall back to Cargo.toml
    for toml in root.rglob("Cargo.toml"):
        content = _safe_read(toml)
        m = re.search(r'godot\s*=\s*\{[^}]*version\s*=\s*"([^"]+)"', content)
        if m:
            return m.group(1)
        m = re.search(r'godot\s*=\s*"([^"]+)"', content)
        if m:
            return m.group(1)
    return None


def _find_api_feature(root: Path) -> str | None:
    for toml in root.rglob("Cargo.toml"):
        content = _safe_read(toml)
        m = re.search(r'"(api-4-\d+)"', content)
        if m:
            return m.group(1)
    return None


def _get_godot_version(godot_bin: str) -> str | None:
    try:
        result = subprocess.run(
            [godot_bin, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _compatibility_warnings(
    gdext_version: str | None,
    godot_version: str | None,
    api_feature: str | None,
) -> list[str]:
    warnings = []
    if gdext_version is None:
        warnings.append("gdext not found in Cargo.toml — add: godot = \"0.2\"")
    if godot_version is None:
        warnings.append("Godot binary not found in PATH — set GODOT_BIN env var")
    if api_feature is None and gdext_version is not None:
        warnings.append("No api-4-x feature flag set — gdext will use its bundled API version")

    # Version cross-check
    if gdext_version and godot_version and api_feature:
        # Extract major.minor from godot version string (e.g. "4.3.stable")
        gv_match = re.search(r"4\.(\d+)", godot_version)
        feat_match = re.search(r"api-4-(\d+)", api_feature)
        if gv_match and feat_match:
            godot_minor = int(gv_match.group(1))
            api_minor = int(feat_match.group(1))
            if api_minor > godot_minor:
                warnings.append(
                    f"api-{api_feature} targets Godot 4.{api_minor} but binary is 4.{godot_minor} "
                    f"— method hash mismatch may cause runtime crashes"
                )
            elif api_minor < godot_minor:
                warnings.append(
                    f"api-{api_feature} targets Godot 4.{api_minor} but binary is 4.{godot_minor} "
                    f"— consider upgrading: features = [\"{api_feature[:5]}{godot_minor}\"]"
                )
    return warnings
