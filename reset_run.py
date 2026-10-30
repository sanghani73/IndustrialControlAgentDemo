"""Clean up dynamic data and re-anchor the production plan for a new demo.

Clears collections that accumulate per-run data:
  - plant_alarms
  - correlated_alarm_groups
  - action_queue
  - sensor_telemetry

Re-anchors the production plan and actuals to the current wall-clock time
by re-running seed_production_plan(). This resets:
  - production_plans         (plan window + batch planned_start/end anchored to now)
  - production_actuals       (one running batch, no delays, 0 deviation)
  - automation_policies      (unchanged reference data, re-asserted)

Does NOT touch other seeded reference data:
  - plant_sops, equipment_registry, alarm_definitions, incident_history

Does NOT drop or rebuild indexes (standard or Atlas Vector Search).

Usage:
    python reset_run.py
"""

from config import db
from seed.seed_production_plan import seed_production_plan


DYNAMIC_COLLECTIONS = [
    "plant_alarms",
    "correlated_alarm_groups",
    "action_queue",
    "sensor_telemetry",
]


def clear_dynamic_collections() -> dict[str, int]:
    cleared = {}
    existing = set(db.list_collection_names())
    for name in DYNAMIC_COLLECTIONS:
        if name not in existing:
            cleared[name] = 0
            continue
        count = db[name].count_documents({})
        db[name].delete_many({})
        cleared[name] = count
    return cleared


def main():
    print("=" * 60)
    print("  Resetting demo state (dynamic collections + production plan)")
    print("=" * 60)
    print(f"  Target database: {db.name}")
    print()

    cleared = clear_dynamic_collections()
    for name, count in cleared.items():
        print(f"  Cleared {name:28s} ({count} docs)")

    print()
    print("  Re-anchoring production plan to current time...")
    seed_production_plan()

    total = sum(cleared.values())
    print()
    print(f"  Done — removed {total} dynamic docs and re-anchored the plan.")
    print("  Reference data (SOPs, equipment, alarm defs, incidents) untouched.")
    print("  Restart the agents to pick up the clean state.")


if __name__ == "__main__":
    main()
