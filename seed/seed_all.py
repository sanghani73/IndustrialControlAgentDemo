import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import ASCENDING, DESCENDING
from pymongo.operations import SearchIndexModel

from config import db
from seed.seed_equipment import seed_equipment
from seed.seed_alarm_definitions import seed_alarm_definitions
from seed.seed_sops import seed_sops
from seed.seed_incidents import seed_incidents
from seed.seed_production_plan import seed_production_plan


# ---------------------------------------------------------------------------
# 0. Clear dynamic collections (reset between demo runs)
# ---------------------------------------------------------------------------

DYNAMIC_COLLECTIONS = [
    "plant_alarms",
    "correlated_alarm_groups",
    "action_queue",
    "sensor_telemetry",
]


def clear_dynamic_collections():
    for coll_name in DYNAMIC_COLLECTIONS:
        if coll_name not in db.list_collection_names():
            continue
        count = db[coll_name].count_documents({})
        db[coll_name].delete_many({})
        print(f"  -> Cleared {coll_name} ({count} docs)")


# ---------------------------------------------------------------------------
# 1. Time Series Collection
# ---------------------------------------------------------------------------

def ensure_time_series_collection():
    if "sensor_telemetry" not in db.list_collection_names():
        db.create_collection(
            "sensor_telemetry",
            timeseries={
                "timeField": "timestamp",
                "metaField": "metadata",
                "granularity": "seconds",
            },
        )
        print("  -> Created Time Series collection: 'sensor_telemetry'")
    else:
        print("  -> Time Series collection 'sensor_telemetry' already exists.")


# ---------------------------------------------------------------------------
# 2. Standard Indexes
# ---------------------------------------------------------------------------

STANDARD_INDEXES = {
    "sensor_telemetry": [
        (
            [("metadata.area", ASCENDING), ("metadata.subsystem", ASCENDING), ("timestamp", DESCENDING)],
            "area_subsystem_ts",
        ),
    ],
    "plant_alarms": [
        ([("area", ASCENDING), ("timestamp", DESCENDING)], "area_ts"),
        ([("correlation_group_id", ASCENDING)], "corr_group"),
        ([("correlated", ASCENDING), ("timestamp", DESCENDING)], "correlated_ts"),
    ],
    "correlated_alarm_groups": [
        ([("status", ASCENDING), ("created_at", DESCENDING)], "status_created"),
        ([("area", ASCENDING), ("subsystem", ASCENDING)], "area_subsystem"),
    ],
    "equipment_registry": [
        ([("tag", ASCENDING)], "tag_unique"),
        ([("area", ASCENDING), ("subsystem", ASCENDING)], "area_subsystem"),
    ],
    "alarm_definitions": [
        ([("alarm_code", ASCENDING)], "alarm_code_unique"),
        ([("root_cause_group", ASCENDING)], "root_cause_group"),
        ([("event_pattern", ASCENDING)], "event_pattern"),
    ],
    "incident_history": [
        ([("area", ASCENDING), ("subsystem", ASCENDING), ("timestamp", DESCENDING)], "area_sub_ts"),
        ([("root_cause_group", ASCENDING)], "root_cause_group"),
    ],
    "action_queue": [
        ([("status", ASCENDING), ("created_at", DESCENDING)], "status_created"),
        ([("area", ASCENDING), ("status", ASCENDING)], "area_status"),
        ([("correlation_group_id", ASCENDING)], "corr_group"),
    ],
    "automation_policies": [
        ([("action_type", ASCENDING), ("area", ASCENDING), ("subsystem", ASCENDING)], "action_area_sub"),
    ],
    "production_plans": [
        ([("area", ASCENDING), ("shift", DESCENDING)], "area_shift"),
    ],
    "production_actuals": [
        ([("batch_name", ASCENDING)], "batch_unique"),
        ([("area", ASCENDING), ("status", ASCENDING)], "area_status"),
    ],
}


def _existing_index_names(collection_name: str) -> set[str]:
    try:
        return {idx["name"] for idx in db[collection_name].list_indexes()}
    except Exception:
        return set()


def create_standard_indexes():
    total = 0
    skipped = 0
    for coll_name, indexes in STANDARD_INDEXES.items():
        existing = _existing_index_names(coll_name)
        for keys, name in indexes:
            if name in existing:
                skipped += 1
                continue
            try:
                unique = name.endswith("_unique")
                db[coll_name].create_index(keys, name=name, unique=unique)
                total += 1
            except Exception as e:
                print(f"  [WARN] Index {name} on {coll_name}: {e}")
    print(f"  -> Created {total} standard index(es), {skipped} already existed.")


# ---------------------------------------------------------------------------
# 3. Atlas Vector Search Indexes (autoEmbed / Voyage AI)
# ---------------------------------------------------------------------------

VECTOR_SEARCH_INDEXES = [
    {
        "collection": "plant_sops",
        "name": "sop_auto_vector_index",
        "definition": {
            "fields": [
                {"type": "autoEmbed", "path": "content", "model": "voyage-4-large", "modality": "text"},
                {"type": "filter", "path": "area"},
                {"type": "filter", "path": "subsystem"},
            ]
        },
    },
    {
        "collection": "alarm_definitions",
        "name": "alarm_def_auto_vector_index",
        "definition": {
            "fields": [
                {"type": "autoEmbed", "path": "description", "model": "voyage-4-large", "modality": "text"},
                {"type": "filter", "path": "area"},
                {"type": "filter", "path": "subsystem"},
            ]
        },
    },
    {
        "collection": "incident_history",
        "name": "incident_auto_vector_index",
        "definition": {
            "fields": [
                {"type": "autoEmbed", "path": "narrative", "model": "voyage-4-large", "modality": "text"},
                {"type": "filter", "path": "area"},
                {"type": "filter", "path": "root_cause_group"},
            ]
        },
    },
]


def _get_search_index_names(collection_name: str) -> dict[str, str]:
    """Return {name: status} for existing search indexes on a collection."""
    try:
        return {
            idx["name"]: idx.get("status", "UNKNOWN")
            for idx in db[collection_name].list_search_indexes()
        }
    except Exception:
        return {}


def create_vector_search_indexes():
    created = 0
    existing = 0

    for spec in VECTOR_SEARCH_INDEXES:
        coll_name = spec["collection"]
        idx_name = spec["name"]
        current = _get_search_index_names(coll_name)

        if idx_name in current:
            status = current[idx_name]
            print(f"  -> {idx_name} on {coll_name} already exists (status: {status})")
            existing += 1
            continue

        try:
            model = SearchIndexModel(
                definition=spec["definition"],
                name=idx_name,
                type="vectorSearch",
            )
            db[coll_name].create_search_index(model)
            print(f"  -> Created {idx_name} on {coll_name}")
            created += 1
        except Exception as e:
            print(f"  [ERROR] Failed to create {idx_name} on {coll_name}: {e}")

    print(f"  -> {created} vector search index(es) created, {existing} already existed.")
    return created


def wait_for_vector_indexes(timeout_seconds: int = 120):
    """Poll until all vector search indexes are READY, or timeout."""
    print(f"  Waiting for vector search indexes to become active (up to {timeout_seconds}s)...")
    deadline = time.time() + timeout_seconds
    pending_names = {spec["name"] for spec in VECTOR_SEARCH_INDEXES}

    while time.time() < deadline and pending_names:
        still_pending = set()
        for spec in VECTOR_SEARCH_INDEXES:
            if spec["name"] not in pending_names:
                continue
            statuses = _get_search_index_names(spec["collection"])
            status = statuses.get(spec["name"], "NOT_FOUND")
            if status in ("READY", "ACTIVE"):
                print(f"  -> {spec['name']}: READY")
            else:
                still_pending.add(spec["name"])

        pending_names = still_pending
        if pending_names:
            time.sleep(5)

    if pending_names:
        print(
            f"  [NOTE] These indexes are still building: {', '.join(pending_names)}\n"
            f"         They will become active shortly. You can check status in the Atlas UI."
        )
    else:
        print("  -> All vector search indexes are active.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def seed_all():
    print("=" * 60)
    print("  Manufacturing Ops — Full Database Seed")
    print("=" * 60)

    print("\n[1/9] Clearing dynamic collections (alarms, actions, telemetry)...")
    clear_dynamic_collections()

    print("\n[2/9] Time Series collection...")
    ensure_time_series_collection()

    print("\n[3/9] Equipment registry...")
    seed_equipment()

    print("\n[4/9] Alarm definitions...")
    seed_alarm_definitions()

    print("\n[5/9] Standard Operating Procedures...")
    seed_sops()

    print("\n[6/9] Historical incidents...")
    seed_incidents()

    print("\n[7/9] Production plan, automation policies & actuals...")
    seed_production_plan()

    print("\n[8/9] Standard indexes...")
    create_standard_indexes()

    print("\n[9/9] Atlas Vector Search indexes...")
    newly_created = create_vector_search_indexes()
    if newly_created > 0:
        wait_for_vector_indexes(timeout_seconds=120)

    print("\n" + "=" * 60)
    print("  Seed complete. All collections, indexes, and data are ready.")
    print("=" * 60)


if __name__ == "__main__":
    seed_all()
