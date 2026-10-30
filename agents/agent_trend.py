"""Agent 2 — Trend Analysis (Predictive Layer)

Runs real sliding-window aggregations on sensor_telemetry using
MongoDB's $setWindowFields + $derivative + rolling $avg. Detects:

  - Dosing flow collapse  (SCN-01):  negative slope on 37-FT-4502
  - Thermal excursion     (SCN-02):  positive slope on 37-TT-4521
  - CIP cavitation        (SCN-03):  negative slope on 30-PT-9041

Each detection emits a PREDICTIVE early-warning alarm to plant_alarms
before the control system's hard-threshold trip fires. The alarm text
contains the predictive event pattern seeded in alarm_definitions, so
the correlator folds the warning into the same root-cause group as the
hard trip when it arrives.
"""

import time
from datetime import datetime, timedelta, timezone

from config import db


POLL_INTERVAL_SECONDS = 10
WINDOW_RANGE_SECONDS = 30
LOOKBACK_SECONDS = 90
DUPLICATE_COOLDOWN_MINUTES = 5


def _recent_duplicate_alarm_exists(
    batch_name: str, tag: str, root_cause_group: str
) -> bool:
    """Suppress re-emission of the same predictive alarm when either (a) a
    recent plant_alarms doc with the same batch+tag already exists, or (b)
    an open correlated group for this batch's root cause is in flight."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_COOLDOWN_MINUTES)
    recent = db.plant_alarms.find_one({
        "batch_name": batch_name,
        "tag": tag,
        "timestamp": {"$gte": cutoff},
    })
    if recent:
        return True
    open_group = db.correlated_alarm_groups.find_one({
        "batch_name": batch_name,
        "root_cause_group": root_cause_group,
        "status": {"$nin": ["resolved", "closed", "completed"]},
    })
    return open_group is not None


def _sliding_window_pipeline(
    area: str,
    subsystem: str,
    measurement_path: str,
    valve_measurement_path: str | None = None,
):
    """Build a pipeline that uses $setWindowFields to compute the rolling
    derivative and rolling average of a measurement over a 30-second time
    window, partitioned by batch. Returns the most recent row per batch so
    we can read the latest slope value."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=LOOKBACK_SECONDS)

    output = {
        "rolling_avg_value": {
            "$avg": f"${measurement_path}",
            "window": {"range": [-WINDOW_RANGE_SECONDS, 0], "unit": "second"},
        },
        "slope_per_sec": {
            "$derivative": {
                "input": f"${measurement_path}",
                "unit": "second",
            },
            "window": {"range": [-WINDOW_RANGE_SECONDS, 0], "unit": "second"},
        },
    }
    if valve_measurement_path:
        output["rolling_avg_valve"] = {
            "$avg": f"${valve_measurement_path}",
            "window": {"range": [-WINDOW_RANGE_SECONDS, 0], "unit": "second"},
        }

    match_stage = {
        "metadata.area": area,
        "metadata.subsystem": subsystem,
        "timestamp": {"$gte": cutoff},
        # $derivative crashes if input is ever null, so exclude docs that
        # don't carry this measurement (e.g. dosing telemetry mixed into the
        # same subsystem as thermal telemetry).
        measurement_path: {"$ne": None, "$exists": True},
    }
    if valve_measurement_path:
        match_stage[valve_measurement_path] = {"$ne": None, "$exists": True}

    return [
        {"$match": match_stage},
        {"$setWindowFields": {
            "partitionBy": "$metadata.batch_name",
            "sortBy": {"timestamp": 1},
            "output": output,
        }},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$metadata.batch_name",
            "latest_ts": {"$first": "$timestamp"},
            "latest_value": {"$first": f"${measurement_path}"},
            "rolling_avg_value": {"$first": "$rolling_avg_value"},
            "slope_per_sec": {"$first": "$slope_per_sec"},
            **(
                {"rolling_avg_valve": {"$first": "$rolling_avg_valve"}}
                if valve_measurement_path else {}
            ),
            "data_points": {"$sum": 1},
        }},
    ]


def _emit_predictive_alarm(
    *,
    area: str,
    subsystem: str,
    tag: str,
    event: str,
    batch_name: str,
    root_cause_group: str,
    telemetry_context: dict,
):
    if _recent_duplicate_alarm_exists(batch_name, tag, root_cause_group):
        return False
    alarm_doc = {
        "timestamp": datetime.now(timezone.utc),
        "source": f"TrendAgent/{area}/{subsystem}",
        "area": area,
        "subsystem": subsystem,
        "tag": tag,
        "event": event,
        "batch_name": batch_name,
        "type": "PredictiveWarning",
        "severity": "WARNING",
        "telemetry_context": telemetry_context,
        "correlation_group_id": None,
        "correlated": False,
    }
    db.plant_alarms.insert_one(alarm_doc)
    print(f"[AGENT 2] Emitted predictive warning: {event}  (batch={batch_name})")
    return True


def inspect_dosing_gradient_trends(area: str = "Mixer3", subsystem: str = "M3MX3"):
    """SCN-01: flow collapse on 37-FT-4502 with saturated valve."""
    pipeline = _sliding_window_pipeline(
        area, subsystem,
        "measurements.37-FT-4502_flow_rate_kgs",
        valve_measurement_path="measurements.37-VS-4520_valve_pos_pct",
    )
    for row in db.sensor_telemetry.aggregate(pipeline):
        if row.get("data_points", 0) < 3:
            continue
        slope = row.get("slope_per_sec")
        valve = row.get("rolling_avg_valve")
        value = row.get("latest_value")
        if slope is None or valve is None or value is None:
            continue
        if slope < -0.03 and valve > 70.0:
            emitted = _emit_predictive_alarm(
                area=area,
                subsystem=subsystem,
                tag="37-FT-4502",
                event=(
                    f"PREDICTIVE: Dosing flow slope negative "
                    f"({slope:.3f} kg/s per s, current {value:.2f} kg/s, valve {valve:.0f}%)"
                ),
                batch_name=row["_id"],
                root_cause_group="DOSING_STARVATION",
                telemetry_context={
                    "slope_kgs_per_s": round(slope, 4),
                    "latest_flow_kgs": round(value, 3),
                    "rolling_avg_valve_pct": round(valve, 1),
                    "window_seconds": WINDOW_RANGE_SECONDS,
                },
            )
            if emitted:
                _record_production_delay(row["_id"], area)


def inspect_thermal_rise_trends(area: str = "Mixer3", subsystem: str = "M3MX3"):
    """SCN-02: positive temperature slope on 37-TT-4521."""
    pipeline = _sliding_window_pipeline(
        area, subsystem,
        "measurements.37-TT-4521_vessel_temp_c",
    )
    for row in db.sensor_telemetry.aggregate(pipeline):
        if row.get("data_points", 0) < 3:
            continue
        slope = row.get("slope_per_sec")
        avg_temp = row.get("rolling_avg_value")
        value = row.get("latest_value")
        if slope is None or avg_temp is None or value is None:
            continue
        if slope > 0.3 and avg_temp > 68.0:
            _emit_predictive_alarm(
                area=area,
                subsystem=subsystem,
                tag="37-TT-4521",
                event=(
                    f"PREDICTIVE: Vessel temperature slope rising "
                    f"({slope:.2f} degC per s, current {value:.1f} degC)"
                ),
                batch_name=row["_id"],
                root_cause_group="THERMAL_EXCURSION",
                telemetry_context={
                    "slope_c_per_s": round(slope, 3),
                    "latest_temp_c": round(value, 2),
                    "rolling_avg_temp_c": round(avg_temp, 2),
                    "window_seconds": WINDOW_RANGE_SECONDS,
                },
            )


def inspect_cip_pressure_trends(area: str = "Mixer3", subsystem: str = "M3CIP8"):
    """SCN-03: negative pressure slope on 30-PT-9041 (CIP cavitation onset)."""
    pipeline = _sliding_window_pipeline(
        area, subsystem,
        "measurements.30-PT-9041_supply_press_bar",
    )
    for row in db.sensor_telemetry.aggregate(pipeline):
        if row.get("data_points", 0) < 3:
            continue
        slope = row.get("slope_per_sec")
        value = row.get("latest_value")
        if slope is None or value is None:
            continue
        if slope < -0.015 and value < 2.0:
            _emit_predictive_alarm(
                area=area,
                subsystem=subsystem,
                tag="30-PT-9041",
                event=(
                    f"PREDICTIVE: CIP supply pressure slope dropping "
                    f"({slope:.3f} bar per s, current {value:.2f} bar)"
                ),
                batch_name=row["_id"],
                root_cause_group="CIP_CAVITATION",
                telemetry_context={
                    "slope_bar_per_s": round(slope, 4),
                    "latest_pressure_bar": round(value, 3),
                    "window_seconds": WINDOW_RANGE_SECONDS,
                },
            )


TREND_DELAY_CAUSE = "Trend agent detected predictive degradation"


def _record_production_delay(batch_name: str, area: str):
    actual = db.production_actuals.find_one(
        {"batch_name": batch_name, "area": area}
    )
    if not actual:
        return

    for existing in actual.get("delays", []):
        if (
            existing.get("cause") == TREND_DELAY_CAUSE
            and existing.get("resolved_at") is None
        ):
            return

    now = datetime.now(timezone.utc)
    delay_entry = {
        "delay_type": "alarm_hold",
        "started_at": now,
        "resolved_at": None,
        "duration_minutes": None,
        "cause": TREND_DELAY_CAUSE,
    }
    db.production_actuals.update_one(
        {"batch_name": batch_name},
        {"$push": {"delays": delay_entry}, "$set": {"last_updated": now}},
    )
    print(f"[AGENT 2] Recorded delay for batch {batch_name} in production_actuals.")


def run_trend_monitor(interval_seconds: int = POLL_INTERVAL_SECONDS):
    print(
        f"[AGENT 2] Trend Analysis running every {interval_seconds}s "
        f"(sliding window {WINDOW_RANGE_SECONDS}s via $setWindowFields)..."
    )
    try:
        while True:
            print(f"\n[AGENT 2] Running trend inspection cycle...")
            inspect_dosing_gradient_trends()
            inspect_thermal_rise_trends()
            inspect_cip_pressure_trends()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n[AGENT 2] Trend Monitor terminated.")


if __name__ == "__main__":
    run_trend_monitor()
