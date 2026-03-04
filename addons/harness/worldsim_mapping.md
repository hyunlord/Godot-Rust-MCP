# WorldSim ↔ Harness Interface Mapping

Discovered during integration session (2026-03-04).
This is the living reference for harness ↔ WorldSim integration.

---

## Architecture Note

WorldSim does **not** use Godot autoloads for SimulationEngine or EntityManager.
Both are `RefCounted` objects held as member variables on the `Main` scene node.

Access pattern used by `worldsim_adapter.gd`:
```gdscript
get_tree().root.get_node_or_null("Main").sim_engine
get_tree().root.get_node_or_null("Main").entity_manager
```

---

## Autoloads

| Harness expects         | WorldSim actual                     | Notes                              |
|------------------------|-------------------------------------|------------------------------------|
| /root/SimulationEngine | ❌ not an autoload                  | Use Main.sim_engine via adapter    |
| /root/EntityManager    | ❌ not an autoload                  | Use Main.entity_manager via adapter|
| /root/SettlementManager| ❌ not an autoload                  | Use Main.settlement_manager        |
| —                      | /root/GameConfig                    | Config constants autoload          |
| —                      | /root/SimulationBus                 | Signal bus autoload                |
| —                      | /root/TestHarness (port 9877)       | Existing test harness (--test-harness only) |

---

## Methods

| Harness calls                         | WorldSim actual                          | Notes                               |
|--------------------------------------|------------------------------------------|-------------------------------------|
| engine.process_single_tick()         | sim_engine.advance_ticks(1)              | advance_ticks is headless-safe      |
| engine.reset(seed, n) / reset_simulation() | sim_engine.init_with_seed(seed)   | Resets tick + RNG; entities NOT re-spawned |
| engine.current_tick                  | sim_engine.current_tick                  | Same field name ✅                  |
| mgr.get_all_entities()               | entity_manager.get_alive_entities()      | WorldSim only exposes alive         |
| mgr.get_entity_by_id(id)             | entity_manager.get_entity(id)            | Different method name               |
| mgr.get_alive_count()                | entity_manager.get_alive_count()         | Same name ✅                        |

**Key**: Use `advance_ticks(n)` not `_process_tick()` for headless mode.
`advance_ticks` bypasses the frame accumulator and runs deterministically.

---

## Entity Fields

| Harness expects                  | WorldSim actual          | Type        | Notes                           |
|---------------------------------|--------------------------|-------------|----------------------------------|
| entity.id                       | entity.id                | int         | ✅ same                         |
| entity.is_alive                  | entity.is_alive          | bool        | ✅ same                         |
| entity.name                      | entity.entity_name       | String      | ⚠ different field name          |
| entity.age                       | entity.age               | int (ticks) | ✅ same name; unit is ticks not years |
| entity.health                    | ❌ no health field        | —           | Use hunger+energy as proxy      |
| entity.position                  | entity.position          | Vector2i    | ✅ same; note Vector2**i** not Vector2f |
| entity.needs (dict)              | entity.hunger, .energy, .social | float[0,1] | 3 separate floats, not a dict |
| entity.emotion_data.primary_emotions | entity.emotions      | Dictionary  | Direct dict on entity, not nested |
| entity.emotion_data.stress_level | entity.emotions["stress"]| float[0,1] | In emotions dict                |
| entity.personality_data.axes     | entity.personality.to_dict()["facets"] | Dictionary | HEXACO 24-facet |
| entity.active_traits             | entity.active_traits     | Array       | ✅ same                         |

### WorldSim-specific entity fields (bonus)
- `entity.gender`: "male" / "female"
- `entity.age_stage`: "child" / "adult" / "elder"
- `entity.frailty`: float [0.5, 2.0] — mortality multiplier
- `entity.starving_timer`: int — grace ticks at hunger=0
- `entity.inventory`: `{"food": float, "wood": float, "stone": float}`
- `entity.settlement_id`: int — current settlement
- `entity.partner_id`: int — partner entity ID (-1 = none)
- `entity.current_action`: String — AI state
- `entity.birth_tick`, `entity.birth_date`: birth time

### Emotions dict keys
`happiness`, `loneliness`, `stress`, `grief`, `love` — all float [0.0, 1.0]

---

## Invariant Mapping

Updated 2026-03-04: Invariants now operate on serialized entity dicts from `adapter.get_invariant_entities()`,
not raw RefCounted objects. All 7 invariants confirmed passing with 20 entities in live test.

| Invariant           | Field accessed (serialized)      | Status                                      |
|--------------------|----------------------------------|---------------------------------------------|
| needs_bounded      | `needs` dict (hunger/energy/social) | ✅ adapter synthesizes this dict           |
| emotions_bounded   | `emotions` dict                  | ✅ fixed: was checking `emotion_data.primary_emotions` |
| personality_bounded| `personality_axes` dict (24 HEXACO facets) | ✅ fixed: was checking `personality_data.axes` |
| health_bounded     | `health` key (not present)       | ✅ silently passes — no health field in WorldSim |
| age_non_negative   | `age` int                        | ✅ same field name                          |
| stress_non_negative| `stress_level` float             | ✅ adapter exposes `stress_level` from emotions dict |
| no_duplicate_traits| `active_traits` Array            | ✅ same field name (fixed: `trait` was reserved keyword) |

**Fixes applied (2026-03-04)**:
1. `harness_invariants._get_alive()` now calls `adapter.get_invariant_entities()` → returns serialized dicts
2. `_check_emotions_bounded`: checks `"emotions"` key (not `"emotion_data.primary_emotions"`)
3. `_check_personality_bounded`: checks `"personality_axes"` key (not `"personality_data.axes"`)
4. `_check_no_duplicate_traits`: renamed `for trait in` → `for t in` (`trait` is a GDScript 4.6 reserved word)
5. `worldsim_adapter.get_invariant_entities()`: new method returning serialized entity dicts for invariant use

**Live test result** (Godot 4.6.stable, seed=42, 20 entities, 10 ticks):
```
PING:     pong=True, tick=0
TICK:     ticks_run=10, alive=20, elapsed_ms=17.6ms
SNAPSHOT: alive=20, 20 entities returned
QUERY:    entity 1 has needs/emotions/personality_axes/active_traits ✅
INVARIANT: 7/7 passed ✅
```

---

## Port Conflict

Both `TestHarness` (WorldSim built-in) and `HarnessServer` (our addon) listen on port 9877.

**No conflict in practice**:
- `TestHarness` activates only on `--test-harness` CLI arg
- `HarnessServer` activates only on `--headless` or `--harness` arg
- Never pass both flags simultaneously

---

## Reset Limitation

`godot_reset(seed, agents)` calls `sim_engine.init_with_seed(seed)` which:
- ✅ Resets tick counter to 0
- ✅ Re-seeds the RNG
- ❌ Does NOT re-spawn entities (initial spawn happens in Main._ready())

**Implication**: After reset, entity count is unchanged from startup.
The `agents` parameter is accepted but ignored.
For a true population reset, restart the Godot process.
