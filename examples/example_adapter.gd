extends Node

## Example adapter template for godot-rust-harness.
##
## USAGE:
##   1. Copy this file to addons/harness/myproject_adapter.gd in YOUR project
##   2. Rename the file to match your project (e.g. mygame_adapter.gd)
##   3. Fill in the method bodies to match your project's actual API
##   4. The harness will auto-discover your adapter on startup
##
## The adapter bridges your project's specific API to the harness generic interface.
## Only THIS file needs project-specific knowledge. Harness core stays untouched.
##
## REQUIRED METHODS (harness will call these):
##   get_engine()              -> return your simulation engine node/object
##   get_entity_manager()      -> return your entity manager node/object
##   process_ticks(n: int)     -> advance simulation by n ticks
##   get_current_tick() -> int -> return current simulation tick
##   get_alive_entities() -> Array  -> return array of alive entity objects
##   get_alive_count() -> int  -> return number of alive entities
##   get_entity(id: int)       -> return entity by ID
##   reset_simulation(seed: int, agents: int) -> reset simulation state
##   serialize_entity_summary(e) -> Dictionary  -> lightweight entity dict (for snapshot)
##   serialize_entity_full(e) -> Dictionary     -> full entity dict (for query)
##
## OPTIONAL METHODS:
##   get_invariant_entities() -> Array[Dictionary]
##     If present, invariants receive pre-serialized dicts instead of raw objects.
##     This is RECOMMENDED — it decouples invariant field names from your entity class.


# ==============================================================================
# STEP 1: Define how to find your project's core nodes
# ==============================================================================

func get_engine() -> Object:
	## Return your simulation engine.
	## Examples:
	##   return get_node_or_null("/root/SimulationEngine")
	##   return get_node_or_null("/root/Main").sim_engine
	return null  # <- REPLACE


func get_entity_manager() -> Object:
	## Return your entity manager.
	## Examples:
	##   return get_node_or_null("/root/EntityManager")
	##   return get_node_or_null("/root/Main").entity_manager
	return null  # <- REPLACE


# ==============================================================================
# STEP 2: Define tick control
# ==============================================================================

func process_ticks(n: int) -> void:
	## Advance your simulation by n ticks.
	## Examples:
	##   for i in range(n): get_engine().step()
	##   get_engine().advance_ticks(n)
	pass  # <- REPLACE


func get_current_tick() -> int:
	## Return the current simulation tick number.
	## Examples:
	##   return get_engine().current_tick
	##   return get_engine().tick
	return 0  # <- REPLACE


# ==============================================================================
# STEP 3: Define entity access
# ==============================================================================

func get_alive_entities() -> Array:
	## Return array of alive entity objects.
	## Examples:
	##   return get_entity_manager().get_alive_entities()
	##   return get_entity_manager().get_all_entities().filter(func(e): return e.is_alive)
	return []  # <- REPLACE


func get_alive_count() -> int:
	return get_alive_entities().size()


func get_entity(id: int) -> Object:
	## Return a single entity by ID, or null if not found.
	## Examples:
	##   return get_entity_manager().get_entity(id)
	##   return get_entity_manager().get_entity_by_id(id)
	return null  # <- REPLACE


# ==============================================================================
# STEP 4: Define simulation reset
# ==============================================================================

func reset_simulation(rng_seed: int, agent_count: int) -> void:
	## Reset simulation state with a deterministic seed.
	## Examples:
	##   get_engine().reset(rng_seed, agent_count)
	##   get_engine().init_with_seed(rng_seed)
	pass  # <- REPLACE


# ==============================================================================
# STEP 5: Define entity serialization
# ==============================================================================

func serialize_entity_summary(e: Object) -> Dictionary:
	## Lightweight dict for snapshot (up to 200 entities).
	## Include: id, is_alive, name, position, key stats.
	return {
		"id": e.id,
		"is_alive": e.is_alive,
		# "name": e.name,
		# "age": e.age,
		# "health": e.health,
		# "x": e.position.x,
		# "y": e.position.y,
	}  # <- CUSTOMIZE


func serialize_entity_full(e: Object) -> Dictionary:
	## Full detail dict for single-entity query.
	## Include everything: needs, emotions, personality, traits, etc.
	var d: Dictionary = serialize_entity_summary(e)
	# d["needs"] = {"hunger": e.hunger, "energy": e.energy}
	# d["emotions"] = e.emotions.duplicate()
	# d["personality_axes"] = e.personality.axes.duplicate()
	# d["active_traits"] = e.active_traits.duplicate()
	return d  # <- CUSTOMIZE


func get_invariant_entities() -> Array:
	## RECOMMENDED: return pre-serialized dicts for invariant checks.
	## This decouples invariant field names from your entity class.
	var alive: Array = get_alive_entities()
	var result: Array = []
	for e in alive:
		result.append(serialize_entity_full(e))
	return result
