extends Node

## HarnessInvariants — Extensible registry of simulation invariant checks.
## Each check returns a list of violation dicts. Empty = passed.

var _checks: Dictionary = {}  # {name: Callable}
var _adapter = null  # Optional project-specific adapter


func set_adapter(adapter) -> void:
	_adapter = adapter

const MAX_VIOLATIONS: int = 20


func _ready() -> void:
	_register("needs_bounded", _check_needs_bounded)
	_register("emotions_bounded", _check_emotions_bounded)
	_register("personality_bounded", _check_personality_bounded)
	_register("health_bounded", _check_health_bounded)
	_register("age_non_negative", _check_age_non_negative)
	_register("stress_non_negative", _check_stress_non_negative)
	_register("no_duplicate_traits", _check_no_duplicate_traits)


func _register(name: String, callable: Callable) -> void:
	_checks[name] = callable


## Run one or all invariants. name="" runs all.
func run(name: String) -> Dictionary:
	var results: Array = []
	var names_to_run: Array = []

	if name == "":
		names_to_run = _checks.keys()
	elif _checks.has(name):
		names_to_run = [name]
	else:
		return {
			"error": {
				"code": -32602,
				"message": "Unknown invariant: %s. Available: %s" % [name, ", ".join(_checks.keys())],
			}
		}

	var total_passed: int = 0
	var total_failed: int = 0

	var entities: Array = _get_alive()  # Fetch once for all checks

	for check_name in names_to_run:
		var violations: Array = _checks[check_name].call(entities)
		var passed: bool = violations.is_empty()
		if passed:
			total_passed += 1
		else:
			total_failed += 1
		results.append({
			"name": check_name,
			"passed": passed,
			"violations": violations.slice(0, MAX_VIOLATIONS),
			"violation_count": violations.size(),
			"truncated": violations.size() > MAX_VIOLATIONS,
		})

	return {
		"result": {
			"total": names_to_run.size(),
			"passed": total_passed,
			"failed": total_failed,
			"results": results,
		}
	}


# ── Helpers ────────────────────────────────────────────────────────────────────

func _get_alive() -> Array:
	if _adapter != null:
		# Prefer serialized dicts so invariant field names are project-independent
		if _adapter.has_method("get_invariant_entities"):
			return _adapter.get_invariant_entities()
		return _adapter.get_alive_entities()
	var mgr = get_node_or_null("/root/EntityManager")
	if mgr == null:
		return []
	if not mgr.has_method("get_all_entities"):
		return []
	return mgr.get_all_entities().filter(func(e): return e.is_alive)


func _check_range(entities: Array, field: String, low: float, high: float, label: String) -> Array:
	var violations: Array = []
	for e in entities:
		if not (field in e):
			continue
		var val = e.get(field)
		if typeof(val) == TYPE_DICTIONARY:
			# field is a dict of named values (e.g. needs, emotions)
			for k in val:
				var v = val[k]
				if typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT:
					if v < low or v > high:
						violations.append({
							"entity_id": e.id,
							"field": "%s.%s" % [field, k],
							"value": v,
							"expected": "[%s, %s]" % [low, high],
						})
		elif typeof(val) == TYPE_FLOAT or typeof(val) == TYPE_INT:
			if val < low or val > high:
				violations.append({
					"entity_id": e.id,
					"field": field,
					"value": val,
					"expected": "[%s, %s]" % [low, high],
				})
	return violations


# ── Invariant Implementations ──────────────────────────────────────────────────

func _check_needs_bounded(entities: Array) -> Array:
	var violations: Array = []
	for e in entities:
		if not ("needs" in e):
			continue
		var needs = e.needs
		if typeof(needs) != TYPE_DICTIONARY:
			continue
		for k in needs:
			var v = needs[k]
			if (typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT) and (v < 0.0 or v > 1.0):
				violations.append({
					"entity_id": e.id,
					"field": "needs.%s" % k,
					"value": v,
					"expected": "[0.0, 1.0]",
				})
	return violations


func _check_emotions_bounded(entities: Array) -> Array:
	var violations: Array = []
	for e in entities:
		# Prefer "emotions" dict (serialized form from adapter)
		var emotions = null
		if "emotions" in e:
			emotions = e.get("emotions") if typeof(e) == TYPE_DICTIONARY else e.emotions
		elif "emotion_data" in e:
			var ed = e.get("emotion_data") if typeof(e) == TYPE_DICTIONARY else e.emotion_data
			if ed != null and "primary_emotions" in ed:
				emotions = ed.primary_emotions
			elif typeof(ed) == TYPE_DICTIONARY:
				emotions = ed
		if emotions == null or typeof(emotions) != TYPE_DICTIONARY:
			continue
		var eid = e.get("id") if typeof(e) == TYPE_DICTIONARY else e.id
		for k in emotions:
			var v = emotions[k]
			if (typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT) and (v < 0.0 or v > 1.0):
				violations.append({
					"entity_id": eid,
					"field": "emotions.%s" % k,
					"value": v,
					"expected": "[0.0, 1.0]",
				})
	return violations


func _check_personality_bounded(entities: Array) -> Array:
	var violations: Array = []
	for e in entities:
		# Prefer "personality_axes" dict (serialized form from adapter)
		var axes = null
		if "personality_axes" in e:
			axes = e.get("personality_axes") if typeof(e) == TYPE_DICTIONARY else e.personality_axes
		elif "personality_data" in e:
			var pd = e.get("personality_data") if typeof(e) == TYPE_DICTIONARY else e.personality_data
			if pd == null:
				continue
			if "axes" in pd:
				axes = pd.axes
			elif typeof(pd) == TYPE_DICTIONARY:
				axes = pd
		if axes == null or typeof(axes) != TYPE_DICTIONARY:
			continue
		var eid = e.get("id") if typeof(e) == TYPE_DICTIONARY else e.id
		for k in axes:
			var v = axes[k]
			if (typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT) and (v < 0.0 or v > 1.0):
				violations.append({
					"entity_id": eid,
					"field": "personality.%s" % k,
					"value": v,
					"expected": "[0.0, 1.0]",
				})
	return violations


func _check_health_bounded(entities: Array) -> Array:
	return _check_range(entities, "health", 0.0, 1.0, "health")


func _check_age_non_negative(entities: Array) -> Array:
	var violations: Array = []
	for e in entities:
		if not ("age" in e):
			continue
		var v = e.age
		if (typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT) and v < 0.0:
			violations.append({
				"entity_id": e.id,
				"field": "age",
				"value": v,
				"expected": ">= 0",
			})
	return violations


func _check_stress_non_negative(entities: Array) -> Array:
	var violations: Array = []
	for e in entities:
		var stress_val = null
		if "stress_level" in e:
			stress_val = e.stress_level
		elif "emotion_data" in e and e.emotion_data != null and "stress_level" in e.emotion_data:
			stress_val = e.emotion_data.stress_level
		if stress_val == null:
			continue
		if (typeof(stress_val) == TYPE_FLOAT or typeof(stress_val) == TYPE_INT) and stress_val < 0.0:
			violations.append({
				"entity_id": e.id,
				"field": "stress_level",
				"value": stress_val,
				"expected": ">= 0",
			})
	return violations


func _check_no_duplicate_traits(entities: Array) -> Array:
	var violations: Array = []
	for e in entities:
		if not ("active_traits" in e):
			continue
		var traits = e.active_traits
		if typeof(traits) != TYPE_ARRAY:
			continue
		var seen: Dictionary = {}
		for t in traits:
			var trait_id = null
			if typeof(t) == TYPE_DICTIONARY and "trait_id" in t:
				trait_id = t["trait_id"]
			elif typeof(t) == TYPE_STRING or typeof(t) == TYPE_INT:
				trait_id = t
			if trait_id == null:
				continue
			if trait_id in seen:
				violations.append({
					"entity_id": e.id,
					"field": "active_traits",
					"duplicate_trait_id": trait_id,
				})
			else:
				seen[trait_id] = true
	return violations
