"""Agent 4 — Production Monitor (P1)

Periodically compares production_plans vs production_actuals. Detects
late starts, schedule deviations, and alarm holds. Emits deviation
warnings to plant_alarms and the dashboard.
"""

import time
from datetime import datetime, timedelta, timezone

from config import db


def _ensure_aware(dt):
    """Make a datetime timezone-aware (UTC) if it isn't already."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_current_shift_plan(area: str = "Mixer3"):
    """Find the production plan whose shift window covers the current time."""
    now = datetime.now(timezone.utc)

    plans = list(db.production_plans.find({"area": area}).sort("shift", -1).limit(5))

    for plan in plans:
        shift_str = plan.get("shift", "")
        if "/" not in shift_str:
            continue
        start_str, end_str = shift_str.split("/", 1)
        try:
            shift_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            shift_end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        if shift_start <= now <= shift_end:
            return plan

    if plans:
        return plans[0]
    return None


RESOLVED_GROUP_STATUSES = {"resolved", "closed", "completed"}
TERMINAL_ACTION_STATUSES = ("completed", "rejected")


def _close_groups_for_completed_actions(area: str) -> list[dict]:
    """When an action_queue entry hits a terminal state (completed/rejected),
    mark its correlated alarm group as resolved so the behind-schedule
    deviation stops growing. Returns the list of groups just closed."""
    completed_actions = list(
        db.action_queue.find({
            "area": area,
            "status": {"$in": list(TERMINAL_ACTION_STATUSES)},
        }, {"correlation_group_id": 1, "status": 1, "batch_name": 1})
    )
    group_ids = [
        a.get("correlation_group_id") for a in completed_actions
        if a.get("correlation_group_id")
    ]
    if not group_ids:
        return []

    open_groups = list(db.correlated_alarm_groups.find({
        "group_id": {"$in": group_ids},
        "status": {"$nin": list(RESOLVED_GROUP_STATUSES)},
    }))
    if not open_groups:
        return []

    now = datetime.now(timezone.utc)
    for g in open_groups:
        db.correlated_alarm_groups.update_one(
            {"group_id": g["group_id"]},
            {"$set": {"status": "resolved", "resolved_at": now}},
        )
        _resolve_batch_delays(g.get("batch_name", ""), now)
    return open_groups


def _resolve_batch_delays(batch_name: str, resolved_at: datetime):
    """Mark every open delay on the batch as resolved and set its final
    duration_minutes. Done in Python so each delay's duration is computed
    from its own started_at timestamp."""
    if not batch_name:
        return
    actual = db.production_actuals.find_one({"batch_name": batch_name})
    if not actual:
        return
    updated = False
    for delay in actual.get("delays", []):
        if delay.get("resolved_at") is None:
            started = _ensure_aware(delay.get("started_at"))
            if started is not None:
                delay["duration_minutes"] = round(
                    (resolved_at - started).total_seconds() / 60, 1
                )
            delay["resolved_at"] = resolved_at
            updated = True
    if updated:
        db.production_actuals.update_one(
            {"batch_name": batch_name},
            {"$set": {"delays": actual["delays"], "last_updated": resolved_at}},
        )


ACTIONABLE_GROUP_SEVERITIES = ("HIGH", "CRITICAL")


def _active_alarm_groups_for_batch(area: str, subsystem_hint: str | None, actual_start):
    """Return correlated alarm groups in the same area that are still open
    and were created at or after this batch started running. Only groups
    whose highest severity is HIGH/CRITICAL count — WARNING-severity groups
    come from the Trend agent's predictive alarms and are informational;
    they must not keep the batch flagged as 'behind schedule' indefinitely."""
    query = {
        "area": area,
        "highest_severity": {"$in": list(ACTIONABLE_GROUP_SEVERITIES)},
    }
    if actual_start is not None:
        query["created_at"] = {"$gte": actual_start}
    groups = list(db.correlated_alarm_groups.find(query))
    return [
        g for g in groups
        if g.get("status") not in RESOLVED_GROUP_STATUSES
    ]


def _was_deviation_emitted_recently(batch_name: str, deviation_type: str) -> bool:
    """Check if we already emitted this deviation in the last 5 minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    existing = db.plant_alarms.find_one({
        "type": "ProductionDeviation",
        "batch_name": batch_name,
        "event": {"$regex": deviation_type},
        "timestamp": {"$gte": cutoff},
    })
    return existing is not None


def _emit_deviation_alarm(
    batch_name: str,
    area: str,
    deviation_type: str,
    message: str,
    deviation_minutes: float = 0,
):
    if _was_deviation_emitted_recently(batch_name, deviation_type):
        return

    alarm_doc = {
        "timestamp": datetime.now(timezone.utc),
        "source": f"ProductionMonitor/{area}",
        "area": area,
        "subsystem": "",
        "tag": "",
        "event": f"Production deviation ({deviation_type}): {message}",
        "batch_name": batch_name,
        "type": "ProductionDeviation",
        "severity": "WARNING",
        "telemetry_context": {
            "deviation_type": deviation_type,
            "deviation_minutes": deviation_minutes,
        },
        "correlation_group_id": None,
        "correlated": False,
    }
    db.plant_alarms.insert_one(alarm_doc)
    print(f"[AGENT 4] Deviation emitted: {deviation_type} on batch {batch_name}")


def check_production_status(area: str = "Mixer3"):
    now = datetime.now(timezone.utc)
    plan = _get_current_shift_plan(area)

    if not plan:
        print("[AGENT 4] No production plan found for current shift.")
        return

    print(f"[AGENT 4] Checking plan: {plan['plan_id']}")

    # Close any alarm groups whose remediation action has reached a terminal
    # state. Emit a one-shot deviation_resolved event per newly closed group.
    for closed in _close_groups_for_completed_actions(area):
        batch = closed.get("batch_name", "")
        created = _ensure_aware(closed.get("created_at"))
        resolved = _ensure_aware(closed.get("resolved_at")) or now
        hold = (resolved - created).total_seconds() / 60 if created else 0
        _emit_deviation_alarm(
            batch,
            area,
            "deviation_resolved",
            f"Batch {batch} alarm event {closed.get('root_cause_group', '?')} "
            f"resolved after {hold:.0f} min",
            hold,
        )
        print(
            f"[AGENT 4] Closed alarm group {closed.get('group_id')} on batch {batch} "
            f"(hold {hold:.0f} min)"
        )

    for pb in plan.get("planned_batches", []):
        batch_name = pb["batch_name"]
        planned_start = _ensure_aware(pb.get("planned_start"))
        planned_end = _ensure_aware(pb.get("planned_end"))

        if not planned_start or not planned_end:
            continue

        actual = db.production_actuals.find_one({"batch_name": batch_name})

        # Late start detection
        if pb["status"] == "pending" and now > planned_start + timedelta(minutes=10):
            if not actual or actual.get("status") == "pending":
                delay_min = (now - planned_start).total_seconds() / 60
                _emit_deviation_alarm(
                    batch_name,
                    area,
                    "late_start",
                    f"Batch {batch_name} is {delay_min:.0f} min past planned start",
                    delay_min,
                )
                print(
                    f"[AGENT 4] Late start: {batch_name} — "
                    f"{delay_min:.0f} min past planned start"
                )

        # Behind schedule detection
        if actual and actual.get("status") == "running":
            actual_start = _ensure_aware(actual.get("actual_start"))

            # Primary signal: any open correlated alarm group in this area that
            # was created after the batch started running. The group's elapsed
            # time is the current hold duration.
            open_groups = _active_alarm_groups_for_batch(
                area, pb.get("subsystem"), actual_start
            )
            group_hold_minutes = 0.0
            if open_groups:
                earliest = min(
                    _ensure_aware(g["created_at"]) for g in open_groups
                )
                group_hold_minutes = (now - earliest).total_seconds() / 60

            # Secondary signal: whatever deviation other agents/sim have written
            seeded_deviation = actual.get("deviation_from_plan_minutes", 0) or 0
            deviation = max(group_hold_minutes, float(seeded_deviation))

            # Fire if there's an open alarm group (deviation is by definition
            # growing) or if seeded deviation has crossed the 10-minute threshold.
            if open_groups or deviation > 10:
                _emit_deviation_alarm(
                    batch_name,
                    area,
                    "behind_schedule",
                    f"Batch {batch_name} is {deviation:.0f} min behind schedule"
                    + (
                        f" ({len(open_groups)} open alarm group(s): "
                        f"{', '.join(g.get('root_cause_group', '?') for g in open_groups)})"
                        if open_groups else ""
                    ),
                    deviation,
                )
                print(
                    f"[AGENT 4] Behind schedule: {batch_name} — "
                    f"{deviation:.0f} min deviation"
                )
                # Reflect the growing deviation back onto the actuals doc so
                # the dashboard shows the live number.
                db.production_actuals.update_one(
                    {"batch_name": batch_name},
                    {"$set": {
                        "deviation_from_plan_minutes": round(deviation, 1),
                        "last_updated": now,
                    }},
                )

            # Projected finish time = actual_start + planned_duration + deviation.
            # Written to actuals so the dashboard can show live slippage.
            if actual_start:
                planned_dur = pb.get("planned_duration_minutes", 150)
                projected_finish = actual_start + timedelta(
                    minutes=planned_dur + deviation
                )
                db.production_actuals.update_one(
                    {"batch_name": batch_name},
                    {"$set": {
                        "projected_finish_at": projected_finish,
                        "last_updated": now,
                    }},
                )

            # Alarm hold detection (delays recorded by Agent 2 or others)
            delays = actual.get("delays", [])
            active_delays = [
                d for d in delays if d.get("resolved_at") is None
            ]
            if active_delays:
                for delay in active_delays:
                    _emit_deviation_alarm(
                        batch_name,
                        area,
                        "alarm_hold",
                        f"Batch {batch_name} held: {delay.get('cause', 'unknown')}",
                    )
                    print(
                        f"[AGENT 4] Alarm hold: {batch_name} — "
                        f"{delay.get('cause', 'unknown')}"
                    )


def run_production_monitor(interval_seconds: int = 15):
    print(
        f"[AGENT 4] Production Monitor running every {interval_seconds}s..."
    )
    try:
        while True:
            print(f"\n[AGENT 4] Running production check cycle...")
            check_production_status()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[AGENT 4] Production Monitor terminated.")


if __name__ == "__main__":
    run_production_monitor()
