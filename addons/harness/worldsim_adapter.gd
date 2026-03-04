extends Node

## WorldSimAdapter — bridges harness generic interface to WorldSim's Main-hosted objects.
## WorldSim uses RefCounted objects (not autoloads) for SimulationEngine and EntityManager.
## Both are accessed through the Main scene node at /root/Main.
##
## Edit ONLY this file when WorldSim's API changes. Harness core stays untouched.


func _get_main() -> Node:
	return get_tree().root.get_node_or_null("Main")


# ── Engine ──────────────────────────────────────────────────────────────────

func get_engine() -> RefCounted:
	var main := _get_main()
	if main == null:
		return null
	return main.sim_engine


func get_entity_manager() -> RefCounted:
	var main := _get_main()
	if main == null:
		return null
	return main.entity_manager


# ── Tick ─────────────────────────────────────────────────────────────────────

## Advance simulation by n ticks using WorldSim's headless-safe advance_ticks().
func process_ticks(n: int) -> void:
	var main := _get_main()
	if main == null or main.sim_engine == null:
		return
	main.sim_engine.advance_ticks(n)


func get_current_tick() -> int:
	var main := _get_main()
	if main == null or main.sim_engine == null:
		return 0
	return main.sim_engine.current_tick


# ── Entity access ─────────────────────────────────────────────────────────────

func get_alive_entities() -> Array:
	var main := _get_main()
	if main == null or main.entity_manager == null:
		return []
	return main.entity_manager.get_alive_entities()


func get_alive_count() -> int:
	var main := _get_main()
	if main == null or main.entity_manager == null:
		return 0
	return main.entity_manager.get_alive_count()


func get_entity(id: int) -> RefCounted:
	var main := _get_main()
	if main == null or main.entity_manager == null:
		return null
	return main.entity_manager.get_entity(id)


# ── Reset ─────────────────────────────────────────────────────────────────────

## Returns serialized entity dicts for invariant checks.
## Invariants operate on these normalized dicts so field names are project-independent.
func get_invariant_entities() -> Array:
	var alive: Array = get_alive_entities()
	var result: Array = []
	for i in range(alive.size()):
		result.append(serialize_entity_full(alive[i]))
	return result


## Reset simulation: re-seeds engine RNG and resets tick counter.
## Note: entity population is NOT re-spawned (WorldSim spawns via Main._ready()).
## For full population reset, restart Godot with a fresh seed.
func reset_simulation(rng_seed: int, _agent_count: int) -> void:
	var main := _get_main()
	if main == null or main.sim_engine == null:
		return
	main.sim_engine.init_with_seed(rng_seed)


# ── Entity serialization ──────────────────────────────────────────────────────

## Summary used by snapshot (lightweight, up to 200 entities).
func serialize_entity_summary(e: RefCounted) -> Dictionary:
	return {
		"id": e.id,
		"is_alive": e.is_alive,
		"name": e.entity_name,
		"age": e.age,
		"hunger": e.hunger,
		"energy": e.energy,
		"social": e.social,
		"x": e.position.x,
		"y": e.position.y,
	}


## Full detail used by query (single entity, all fields).
func serialize_entity_full(e: RefCounted) -> Dictionary:
	var d: Dictionary = serialize_entity_summary(e)
	d["gender"] = e.gender
	d["age_stage"] = e.age_stage
	d["frailty"] = e.frailty
	d["speed"] = e.speed
	d["strength"] = e.strength
	d["settlement_id"] = e.settlement_id
	d["current_action"] = e.current_action
	d["current_goal"] = e.current_goal
	d["starving_timer"] = e.starving_timer
	d["inventory"] = e.inventory.duplicate()
	d["partner_id"] = e.partner_id

	# Needs as dict (harness invariants check entity.needs as dict)
	d["needs"] = {"hunger": e.hunger, "energy": e.energy, "social": e.social}

	# Emotions dict: {happiness, loneliness, stress, grief, love} — all [0.0, 1.0]
	d["emotions"] = e.emotions.duplicate()
	d["stress_level"] = e.emotions.get("stress", 0.0)

	# Personality (HEXACO 24-facet). Exposed as personality_axes for invariant checks.
	if e.personality != null and e.personality.has_method("to_dict"):
		var pd: Dictionary = e.personality.to_dict()
		d["personality_axes"] = pd.get("facets", {})

	# Active traits
	d["active_traits"] = e.active_traits.duplicate()

	return d
