"""Agent 3 — Alarm Correlator (P0)

Watches plant_alarms via Change Stream. Groups related alarms into
correlated_alarm_groups using a 5-second debounce window, alarm definitions
(root_cause_group), and equipment dependency chains.
"""

import threading
from datetime import datetime, timedelta, timezone

from config import db

SEVERITY_RANK = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "WARNING": 2}

# Keyed by (area, subsystem, root_cause_group|"UNKNOWN") → threading.Timer
_debounce_timers: dict[tuple, threading.Timer] = {}
_debounce_lock = threading.Lock()


def _lookup_alarm_definition(event_text: str):
    """Find alarm_definitions doc whose event_pattern appears in the event string."""
    for defn in db.alarm_definitions.find():
        if defn["event_pattern"] in event_text:
            return defn
    return None


def _get_dependency_tags(tags: list[str]) -> set[str]:
    """Expand a list of tags with their upstream/downstream dependencies."""
    expanded = set(tags)
    for tag in tags:
        equip = db.equipment_registry.find_one({"tag": tag})
        if not equip:
            continue
        for dep_id in equip.get("upstream_dependencies", []) + equip.get("downstream_dependencies", []):
            dep_equip = db.equipment_registry.find_one({"equipment_id": dep_id})
            if dep_equip:
                expanded.add(dep_equip["tag"])
    return expanded


def _highest_severity(alarms: list[dict]) -> str:
    best = "LOW"
    for a in alarms:
        sev = a.get("severity", "LOW")
        if SEVERITY_RANK.get(sev, 0) > SEVERITY_RANK.get(best, 0):
            best = sev
    return best


def _consolidate_telemetry(alarms: list[dict]) -> dict:
    merged = {}
    for a in alarms:
        ctx = a.get("telemetry_context") or {}
        merged.update(ctx)
    return merged


def _finalize_group(area: str, subsystem: str, root_cause_group: str):
    """Called after debounce timer expires. Collects uncorrelated alarms and creates a group."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=35)

    query = {
        "area": area,
        "subsystem": subsystem,
        "correlated": False,
        "timestamp": {"$gte": window_start, "$lte": now},
    }

    if root_cause_group != "UNKNOWN":
        all_event_patterns = []
        for defn in db.alarm_definitions.find({"root_cause_group": root_cause_group}):
            all_event_patterns.append(defn["event_pattern"])

        if all_event_patterns:
            pattern_regex = "|".join(all_event_patterns)
            query["event"] = {"$regex": pattern_regex}

    alarms = list(db.plant_alarms.find(query).sort("timestamp", 1))

    if not alarms:
        unconstrained = {
            "area": area,
            "subsystem": subsystem,
            "correlated": False,
            "timestamp": {"$gte": window_start, "$lte": now},
        }
        alarms = list(db.plant_alarms.find(unconstrained).sort("timestamp", 1))

    if not alarms:
        return

    tags_involved = list({a["tag"] for a in alarms if a.get("tag")})
    dep_tags = _get_dependency_tags(tags_involved)
    extra_alarms = list(
        db.plant_alarms.find({
            "area": area,
            "correlated": False,
            "tag": {"$in": list(dep_tags - set(tags_involved))},
            "timestamp": {"$gte": window_start, "$lte": now},
        })
    )
    alarms.extend(extra_alarms)

    seen_ids = set()
    unique_alarms = []
    for a in alarms:
        if a["_id"] not in seen_ids:
            seen_ids.add(a["_id"])
            unique_alarms.append(a)
    alarms = unique_alarms

    first_ts = alarms[0]["timestamp"]
    group_id = f"GRP-{first_ts.strftime('%Y%m%d-%H%M%S')}-{subsystem}"

    batch_names = [a.get("batch_name") for a in alarms if a.get("batch_name")]
    batch_name = batch_names[0] if batch_names else "UNKNOWN"

    group_doc = {
        "group_id": group_id,
        "created_at": now,
        "area": area,
        "subsystem": subsystem,
        "batch_name": batch_name,
        "root_cause_group": root_cause_group,
        "alarm_ids": [a["_id"] for a in alarms],
        "alarm_events": [a.get("event", "") for a in alarms],
        "tags_involved": list({a["tag"] for a in alarms if a.get("tag")}),
        "highest_severity": _highest_severity(alarms),
        "consolidated_telemetry": _consolidate_telemetry(alarms),
        "status": "pending_remediation",
    }

    db.correlated_alarm_groups.insert_one(group_doc)
    print(
        f"[AGENT 3] Created correlated group {group_id}: "
        f"{len(alarms)} alarm(s), root_cause={root_cause_group}, "
        f"severity={group_doc['highest_severity']}"
    )

    alarm_ids = [a["_id"] for a in alarms]
    db.plant_alarms.update_many(
        {"_id": {"$in": alarm_ids}},
        {"$set": {"correlated": True, "correlation_group_id": group_id}},
    )


def _handle_alarm(alarm_doc: dict):
    """Process a single incoming alarm — lookup definition, schedule debounce."""
    event = alarm_doc.get("event", "")
    area = alarm_doc.get("area", "")
    subsystem = alarm_doc.get("subsystem", "")

    defn = _lookup_alarm_definition(event)
    root_cause_group = defn["root_cause_group"] if defn else "UNKNOWN"

    key = (area, subsystem, root_cause_group)

    print(
        f"[AGENT 3] Alarm received: '{event}' | "
        f"root_cause_group={root_cause_group} | debounce key={key}"
    )

    with _debounce_lock:
        existing = _debounce_timers.get(key)
        if existing:
            existing.cancel()

        timer = threading.Timer(
            5.0, _finalize_group, args=(area, subsystem, root_cause_group)
        )
        timer.daemon = True
        _debounce_timers[key] = timer
        timer.start()


def run_correlator():
    print("[AGENT 3] Alarm Correlator listening on 'plant_alarms' via Change Stream...")
    pipeline = [{
        "$match": {
            "operationType": "insert",
            # ProductionDeviation alarms are meta-events emitted by Agent 4
            # about the current plant state, not operational alarms. They must
            # not form their own correlated groups or they'd re-feed Agent 1.
            "fullDocument.type": {"$ne": "ProductionDeviation"},
        }
    }]
    try:
        with db.plant_alarms.watch(pipeline) as stream:
            for change in stream:
                doc = change.get("fullDocument")
                if doc and not doc.get("correlated", False):
                    _handle_alarm(doc)
    except KeyboardInterrupt:
        print("\n[AGENT 3] Alarm Correlator terminated.")


if __name__ == "__main__":
    run_correlator()
