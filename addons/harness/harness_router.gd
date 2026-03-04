extends Node

## HarnessRouter — JSON-RPC method dispatcher for the Godot harness.
## Instantiated as a child of HarnessServer. Routes all WebSocket commands.

const TICK_METHODS: Array = ["process_single_tick", "_process_tick", "step"]
const ENGINE_PATHS: Array = ["/root/SimulationEngine", "/root/SimEngine", "/root/Simulation",
							  "/root/GameManager", "/root/World"]

var _tick_counter: int = 0
var _engine = null  # Lazily resolved SimulationEngine reference
var _adapter = null  # Optional project-specific adapter


func set_adapter(adapter) -> void:
	_adapter = adapter


func execute(method: String, params: Dictionary) -> Dictionary:
	match method:
		"ping":        return _cmd_ping(params)
		"tick":        return _cmd_tick(params)
		"snapshot":    return _cmd_snapshot(params)
		"query":       return _cmd_query(params)
		"scene_tree":  return _cmd_scene_tree(params)
		"invariant":   return _cmd_invariant(params)
		"reset":       return _cmd_reset(params)
		"bench":       return _cmd_bench(params)
		"force_event": return _cmd_force_event(params)
		"set_config":  return _cmd_set_config(params)
		"golden_dump": return _cmd_golden_dump(params)
		_:
			return _err(-32601, "Method not found: %s" % method)


# ── Internal helpers ──────────────────────────────────────────────────────────

func _ok(result: Dictionary) -> Dictionary:
	return {"result": result}


func _err(code: int, message: String) -> Dictionary:
	return {"error": {"code": code, "message": message}}


func _get_engine():
	if _adapter != null:
		return _adapter.get_engine()
	if _engine != null and is_instance_valid(_engine):
		return _engine
	for candidate in ENGINE_PATHS:
		var node = get_node_or_null(candidate)
		if node != null:
			_engine = node
			return _engine
	return null


func _get_entity_by_id(mgr, id: int):
	if mgr.has_method("get_entity_by_id"):
		return mgr.get_entity_by_id(id)
	if mgr.has_method("get_all_entities"):
		for e in mgr.get_all_entities():
			if e.id == id:
				return e
	return null


func _resolve_tick_method(engine) -> String:
	for m in TICK_METHODS:
		if engine.has_method(m):
			return m
	return ""


func _get_entity_manager():
	if _adapter != null:
		return _adapter.get_entity_manager()
	return get_node_or_null("/root/EntityManager")


func _count_alive() -> int:
	var mgr = _get_entity_manager()
	if mgr == null:
		return 0
	if mgr.has_method("get_alive_count"):
		return mgr.get_alive_count()
	if mgr.has_method("get_all_entities"):
		return mgr.get_all_entities().filter(func(e): return e.is_alive).size()
	return 0


# ── Command implementations ───────────────────────────────────────────────────

func _cmd_ping(_params: Dictionary) -> Dictionary:
	return _ok({"pong": true, "tick": _tick_counter})


func _cmd_tick(params: Dictionary) -> Dictionary:
	var n: int = clampi(params.get("n", 1), 1, 100000)

	if _adapter != null:
		var t_start: int = Time.get_ticks_usec()
		_adapter.process_ticks(n)
		_tick_counter += n
		var elapsed_ms: float = (Time.get_ticks_usec() - t_start) / 1000.0
		return _ok({"ticks_run": n, "tick_now": _tick_counter, "elapsed_ms": elapsed_ms, "alive": _count_alive()})

	var engine = _get_engine()
	if engine == null:
		return _err(-32000,
			"SimulationEngine not found. Tried: %s." % ", ".join(ENGINE_PATHS))

	var tick_method: String = _resolve_tick_method(engine)
	if tick_method == "":
		return _err(-32000,
			"SimulationEngine has no tick method. Expected one of: %s" % ", ".join(TICK_METHODS)
		)

	var t_start: int = Time.get_ticks_usec()
	for _i in range(n):
		engine.call(tick_method)
		_tick_counter += 1
	var elapsed_ms: float = (Time.get_ticks_usec() - t_start) / 1000.0

	return _ok({
		"ticks_run": n,
		"tick_now": _tick_counter,
		"elapsed_ms": elapsed_ms,
		"alive": _count_alive(),
	})


func _cmd_snapshot(_params: Dictionary) -> Dictionary:
	if _adapter != null:
		var alive: Array = _adapter.get_alive_entities()
		var alive_count: int = alive.size()
		var cap: int = min(alive_count, 200)
		var entities: Array = []
		for i in range(cap):
			entities.append(_adapter.serialize_entity_summary(alive[i]))
		return _ok({
			"tick": _tick_counter,
			"total_entities": alive_count,
			"alive": alive_count,
			"entities": entities,
			"truncated": alive_count > 200,
		})

	var mgr = _get_entity_manager()
	var entities: Array = []
	var total: int = 0
	var alive_count: int = 0
	var truncated: bool = false

	if mgr != null and mgr.has_method("get_all_entities"):
		var all_entities: Array = mgr.get_all_entities()
		total = all_entities.size()
		var alive_entities: Array = all_entities.filter(func(e): return e.is_alive)
		alive_count = alive_entities.size()
		var cap: int = min(alive_count, 200)
		truncated = alive_count > 200

		for i in range(cap):
			var e = alive_entities[i]
			var entry: Dictionary = {"id": e.id, "is_alive": true}
			if "name" in e: entry["name"] = e.name
			if "age" in e: entry["age"] = e.age
			if "health" in e: entry["health"] = e.health
			if "position" in e:
				entry["x"] = e.position.x
				entry["y"] = e.position.y
			entities.append(entry)

	return _ok({
		"tick": _tick_counter,
		"total_entities": total,
		"alive": alive_count,
		"entities": entities,
		"truncated": truncated,
	})


func _cmd_query(params: Dictionary) -> Dictionary:
	var query_type: String = params.get("type", "entity")
	var target_id: int = params.get("id", -1)

	if query_type == "entity":
		if _adapter != null:
			var entity = _adapter.get_entity(target_id)
			if entity == null:
				return _err(-32602, "Entity not found: id=%d" % target_id)
			return _ok(_adapter.serialize_entity_full(entity))

		var mgr = _get_entity_manager()
		if mgr == null:
			return _err(-32000, "EntityManager not found at /root/EntityManager")

		var entity = _get_entity_by_id(mgr, target_id)
		if entity == null:
			return _err(-32602, "Entity not found: id=%d" % target_id)
		return _ok(_serialize_entity_full(entity))

	elif query_type == "settlement":
		var smgr = get_node_or_null("/root/SettlementManager")
		if smgr == null:
			return _err(-32000, "SettlementManager not found at /root/SettlementManager")

		var settlement = null
		if smgr.has_method("get_settlement_by_id"):
			settlement = smgr.get_settlement_by_id(target_id)

		if settlement == null:
			return _err(-32602, "Settlement not found: id=%d" % target_id)

		var d: Dictionary = {"id": target_id}
		if "name" in settlement: d["name"] = settlement.name
		if "population" in settlement: d["population"] = settlement.population
		if "position" in settlement:
			d["x"] = settlement.position.x
			d["y"] = settlement.position.y
		return _ok(d)

	else:
		return _err(-32602, "Invalid type: %s. Expected 'entity' or 'settlement'" % query_type)


func _serialize_entity_full(e) -> Dictionary:
	var d: Dictionary = {"id": e.id, "is_alive": e.is_alive}
	if "name" in e: d["name"] = e.name
	if "age" in e: d["age"] = e.age
	if "health" in e: d["health"] = e.health
	if "position" in e:
		d["x"] = e.position.x
		d["y"] = e.position.y
	if "needs" in e: d["needs"] = e.needs
	if "emotion_data" in e and e.emotion_data != null:
		var ed = e.emotion_data
		if "primary_emotions" in ed: d["emotions"] = ed.primary_emotions
		if "stress_level" in ed: d["stress_level"] = ed.stress_level
	if "personality_data" in e and e.personality_data != null:
		var pd = e.personality_data
		if "axes" in pd: d["personality_axes"] = pd.axes
	if "active_traits" in e: d["active_traits"] = e.active_traits
	return d


func _cmd_scene_tree(params: Dictionary) -> Dictionary:
	var depth: int = params.get("depth", 3)
	var root: Node = get_tree().get_root()
	return _ok(_tree_node(root, depth))


func _tree_node(node: Node, depth: int) -> Dictionary:
	var d: Dictionary = {"name": node.name, "type": node.get_class()}
	if depth > 0 and node.get_child_count() > 0:
		var children: Array = []
		for child in node.get_children():
			children.append(_tree_node(child, depth - 1))
		d["children"] = children
	return d


func _cmd_invariant(params: Dictionary) -> Dictionary:
	# HarnessInvariants is a sibling node added by HarnessServer
	var inv = get_parent().get_node_or_null("HarnessInvariants")
	if inv == null:
		# Fallback: try as child of this node
		inv = get_node_or_null("HarnessInvariants")
	if inv == null:
		return _err(-32000,
			"HarnessInvariants node not found. Ensure harness_server.gd adds it as a child."
		)
	return inv.run(params.get("name", ""))


func _cmd_reset(params: Dictionary) -> Dictionary:
	var rng_seed: int = params.get("seed", 42)
	var agents: int = params.get("agents", 50)

	if _adapter != null:
		_adapter.reset_simulation(rng_seed, agents)
		_tick_counter = 0
		return _ok({"seed": rng_seed, "agents": agents, "tick": 0})

	var engine = _get_engine()
	if engine == null:
		return _err(-32000,
			"SimulationEngine not found. Cannot reset. Tried: %s." % ", ".join(ENGINE_PATHS))

	if engine.has_method("reset"):
		engine.reset(rng_seed, agents)
	elif engine.has_method("reset_simulation"):
		engine.reset_simulation(rng_seed, agents)

	_tick_counter = 0
	_engine = null  # Re-resolve after reset in case scene changes

	return _ok({"seed": rng_seed, "agents": agents, "tick": 0})


func _cmd_bench(params: Dictionary) -> Dictionary:
	var n: int = clampi(params.get("n", 100), 1, 100000)
	var warmup: int = clampi(params.get("warmup", 10), 0, 10000)

	var times: Array = []

	if _adapter != null:
		# Warmup (not measured)
		if warmup > 0:
			_adapter.process_ticks(warmup)
			_tick_counter += warmup
		# Measure each tick individually
		for _i in range(n):
			var t_start: int = Time.get_ticks_usec()
			_adapter.process_ticks(1)
			_tick_counter += 1
			times.append((Time.get_ticks_usec() - t_start) / 1000.0)
	else:
		var engine = _get_engine()
		if engine == null:
			return _err(-32000, "SimulationEngine not found")
		var tick_method: String = _resolve_tick_method(engine)
		if tick_method == "":
			return _err(-32000, "SimulationEngine has no tick method")
		# Warmup (not measured)
		for _i in range(warmup):
			engine.call(tick_method)
			_tick_counter += 1
		# Measure each tick individually
		for _i in range(n):
			var t_start: int = Time.get_ticks_usec()
			engine.call(tick_method)
			_tick_counter += 1
			times.append((Time.get_ticks_usec() - t_start) / 1000.0)  # ms

	times.sort()

	var total_time: float = 0.0
	for t in times:
		total_time += t
	var avg: float = total_time / times.size() if times.size() > 0 else 0.0
	var p95_idx: int = max(0, int(ceil(times.size() * 0.95)) - 1)
	var median_idx: int = times.size() / 2

	return _ok({
		"ticks": n,
		"agents": _count_alive(),
		"avg_ms": avg,
		"min_ms": times[0] if times.size() > 0 else 0.0,
		"max_ms": times[-1] if times.size() > 0 else 0.0,
		"p95_ms": times[p95_idx] if p95_idx < times.size() else avg,
		"median_ms": times[median_idx] if median_idx < times.size() else avg,
	})


func _cmd_force_event(params: Dictionary) -> Dictionary:
	var entity_id: int = params.get("entity_id", -1)
	var event_type: String = params.get("event_type", "")
	var event_params: Dictionary = params.get("params", {})

	var mgr = _get_entity_manager()
	if mgr == null:
		return _err(-32000, "EntityManager not found")

	var entity = _get_entity_by_id(mgr, entity_id)
	if entity == null:
		return _err(-32602, "Entity not found: id=%d" % entity_id)

	if entity.has_method("apply_event"):
		entity.apply_event(event_type, event_params)
	elif entity.has_method("trigger_event"):
		entity.trigger_event(event_type, event_params)
	else:
		return _err(-32000,
			"Entity has no event method. Expected apply_event(type, params) or trigger_event(type, params)."
		)

	return _ok({"applied": true, "entity_id": entity_id, "event_type": event_type})


func _cmd_set_config(params: Dictionary) -> Dictionary:
	var key: String = params.get("key", "")
	var value = params.get("value", null)

	if key == "":
		return _err(-32602, "key is required")

	var engine = _get_engine()
	if engine != null:
		if engine.has_method("set_config"):
			engine.set_config(key, value)
		elif key in engine:
			engine.set(key, value)

	return _ok({"key": key, "value": value, "applied": true})


func _cmd_golden_dump(params: Dictionary) -> Dictionary:
	var path: String = params.get("path", "user://golden_dump.json")
	var tag: String = params.get("tag", "")

	var mgr = _get_entity_manager()
	var entities_data: Array = []

	if mgr != null and mgr.has_method("get_all_entities"):
		for e in mgr.get_all_entities():
			entities_data.append(_serialize_entity_full(e))

	var dump: Dictionary = {
		"tag": tag,
		"tick": _tick_counter,
		"entities": entities_data,
	}

	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return _err(-32000, "Failed to open file for writing: %s (error: %s)" % [
			path, FileAccess.get_open_error()
		])

	file.store_string(JSON.stringify(dump, "\t"))
	file.close()

	return _ok({"path": path, "entities_count": entities_data.size(), "tick": _tick_counter})
