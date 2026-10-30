from datetime import datetime, timedelta, timezone
import random
import time

from config import db


# ---------------------------------------------------------------------------
# Generic alarm emitter
# ---------------------------------------------------------------------------

def emit_alarm(
    area: str,
    subsystem: str,
    tag: str,
    event: str,
    batch_name: str,
    severity: str,
    telemetry_context: dict,
    source: str | None = None,
    alarm_type: str = "Alarm",
) -> str:
    """Insert a discrete alarm into plant_alarms and return its ObjectId as str."""
    alarm_doc = {
        "timestamp": datetime.now(timezone.utc),
        "source": source or f"PCL/{area}/{subsystem}",
        "area": area,
        "subsystem": subsystem,
        "tag": tag,
        "event": event,
        "batch_name": batch_name,
        "type": alarm_type,
        "severity": severity,
        "telemetry_context": telemetry_context,
        "correlation_group_id": None,
        "correlated": False,
    }
    res = db.plant_alarms.insert_one(alarm_doc)
    print(f"  [ALARM] {event}  (severity={severity}, id={res.inserted_id})")
    return str(res.inserted_id)


# ---------------------------------------------------------------------------
# SCN-01  Dosing Starvation & Negative Flow Gradient
# ---------------------------------------------------------------------------

def stream_degrading_dosing_telemetry(
    batch_name: str = "101279692", steps: int = 12
):
    """Streams sensor data depicting negative flow gradient on 37-FT-4502."""
    print(
        f"\n[SIMULATOR] Streaming degrading dosing telemetry for batch {batch_name} "
        f"({steps} points) ..."
    )
    start_time = datetime.now(timezone.utc) - timedelta(seconds=steps * 5)
    flow = 2.85
    valve = 55.0
    weight = 1200.0

    for i in range(steps):
        ts = start_time + timedelta(seconds=i * 5)

        if i >= 4:
            flow = max(0.45, flow - 0.35 + random.uniform(-0.02, 0.02))
            valve = min(95.0, valve + 6.0)
        else:
            flow += random.uniform(-0.05, 0.05)

        weight += flow * 5.0
        pressure = max(1.3, 2.3 - (i * 0.09))

        doc = {
            "timestamp": ts,
            "metadata": {
                "area": "Mixer3",
                "subsystem": "M3MX3",
                "batch_name": batch_name,
                "recipe_phase": "CHARGEFL",
            },
            "measurements": {
                "37-VS-4520_valve_pos_pct": round(valve, 1),
                "37-FT-4502_flow_rate_kgs": round(flow, 3),
                "37-WT-4521_tank_weight_kg": round(weight, 1),
                "37-PT-4501_inlet_press_bar": round(pressure, 2),
            },
        }
        db.sensor_telemetry.insert_one(doc)
        print(
            f"  -> Point {i+1}/{steps}: Flow={flow:.2f} kg/s, "
            f"Valve={valve:.1f}%, Pressure={pressure:.2f} bar"
        )
        time.sleep(2.0)


def emit_dosing_alarms(batch_name: str = "101279692"):
    """Emit the two characteristic dosing-starvation alarms 3 s apart."""
    print(f"\n[SIMULATOR] Emitting dosing starvation alarms for batch {batch_name} ...")

    emit_alarm(
        area="Mixer3",
        subsystem="M3MX3",
        tag="37-VS-4520",
        event="37-VS-4520 Water Dosing too slow",
        batch_name=batch_name,
        severity="CRITICAL",
        source="PCL/Mixer3/M3MX3/CHARGEFL",
        telemetry_context={
            "current_flow_kgs": 0.48,
            "nominal_flow_kgs": 2.80,
            "current_valve_pos_pct": 95.0,
            "inlet_pressure_bar": 1.38,
        },
    )

    print("  ... waiting 3 s before second alarm ...")
    time.sleep(3)

    emit_alarm(
        area="Mixer3",
        subsystem="M3MX3",
        tag="37-FT-4502",
        event="37-FT-4502 Limit value (high) for the negative gradient",
        batch_name=batch_name,
        severity="HIGH",
        source="PCL/Mixer3/M3MX3/CHARGEFL",
        alarm_type="Warning",
        telemetry_context={
            "current_flow_kgs": 0.45,
            "flow_gradient_kgs2": -0.35,
            "current_valve_pos_pct": 95.0,
            "inlet_pressure_bar": 1.34,
        },
    )


# ---------------------------------------------------------------------------
# SCN-02  Thermal Excursion & Valve Actuator Lag
# ---------------------------------------------------------------------------

def stream_thermal_excursion_telemetry(
    batch_name: str = "101279692", steps: int = 12
):
    """Streams sensor data depicting exothermic temperature rise on 37-TT-4521."""
    print(
        f"\n[SIMULATOR] Streaming thermal excursion telemetry for batch {batch_name} "
        f"({steps} points) ..."
    )
    start_time = datetime.now(timezone.utc) - timedelta(seconds=steps * 5)
    temp = 65.0
    tcv_readback = 50.0
    conductivity = 4.2

    for i in range(steps):
        ts = start_time + timedelta(seconds=i * 5)

        if i >= 3:
            temp += random.uniform(1.8, 2.5)
            tcv_readback = max(12.0, tcv_readback - random.uniform(3.0, 5.0))
        else:
            temp += random.uniform(0.3, 0.8)
            tcv_readback += random.uniform(-1.0, 1.0)

        conductivity += random.uniform(-0.1, 0.15)

        doc = {
            "timestamp": ts,
            "metadata": {
                "area": "Mixer3",
                "subsystem": "M3MX3",
                "batch_name": batch_name,
                "recipe_phase": "HEATCOOL",
            },
            "measurements": {
                "37-TT-4521_vessel_temp_c": round(temp, 2),
                "37-TCV-4521_valve_readback_pct": round(tcv_readback, 1),
                "37-CM-4590_conductivity_ms": round(conductivity, 2),
            },
        }
        db.sensor_telemetry.insert_one(doc)
        print(
            f"  -> Point {i+1}/{steps}: Temp={temp:.1f}°C, "
            f"TCV-Rbk={tcv_readback:.1f}%, Cond={conductivity:.2f} mS"
        )
        time.sleep(2.0)


def emit_thermal_alarms(batch_name: str = "101279692"):
    """Emit thermal excursion alarms 2 s apart."""
    print(f"\n[SIMULATOR] Emitting thermal excursion alarms for batch {batch_name} ...")

    emit_alarm(
        area="Mixer3",
        subsystem="M3MX3",
        tag="37-TT-4521",
        event="37-TT-4521 PV - High alarm limit violated",
        batch_name=batch_name,
        severity="CRITICAL",
        source="PCL/Mixer3/M3MX3/HEATCOOL",
        telemetry_context={
            "current_temp_c": 84.3,
            "high_alarm_limit_c": 82.0,
            "tcv_readback_pct": 15.2,
            "conductivity_ms": 4.45,
        },
    )

    print("  ... waiting 2 s before second alarm ...")
    time.sleep(2)

    emit_alarm(
        area="Mixer3",
        subsystem="M3MX3",
        tag="37-TCV-4521",
        event="37-TCV-4521 Rbk - Low warning limit violated",
        batch_name=batch_name,
        severity="HIGH",
        source="PCL/Mixer3/M3MX3/HEATCOOL",
        alarm_type="Warning",
        telemetry_context={
            "tcv_readback_pct": 14.8,
            "tcv_setpoint_pct": 50.0,
            "vessel_temp_c": 84.7,
        },
    )


# ---------------------------------------------------------------------------
# SCN-03  CIP Loop Cavitation & Starvation
# ---------------------------------------------------------------------------

def stream_cip_cavitation_telemetry(
    batch_name: str = "M3CIP_R708", steps: int = 10
):
    """Streams CIP loop telemetry showing flow starvation and pressure drop."""
    print(
        f"\n[SIMULATOR] Streaming CIP cavitation telemetry for batch {batch_name} "
        f"({steps} points) ..."
    )
    start_time = datetime.now(timezone.utc) - timedelta(seconds=steps * 5)
    flow = 3.8
    return_flow = 3.5
    pressure = 2.6

    for i in range(steps):
        ts = start_time + timedelta(seconds=i * 5)

        if i >= 3:
            flow = max(0.9, flow - random.uniform(0.3, 0.5))
            return_flow = max(0.6, return_flow - random.uniform(0.25, 0.45))
            pressure = max(0.8, pressure - random.uniform(0.15, 0.25))
        else:
            flow += random.uniform(-0.05, 0.05)
            return_flow += random.uniform(-0.05, 0.05)
            pressure += random.uniform(-0.03, 0.03)

        doc = {
            "timestamp": ts,
            "metadata": {
                "area": "Mixer3",
                "subsystem": "M3CIP8",
                "batch_name": batch_name,
                "recipe_phase": "CIP",
            },
            "measurements": {
                "30-FIC-9031_flow_rate_lpm": round(flow, 2),
                "30-FT-9041_return_flow_lpm": round(return_flow, 2),
                "30-PT-9041_supply_press_bar": round(pressure, 2),
            },
        }
        db.sensor_telemetry.insert_one(doc)
        print(
            f"  -> Point {i+1}/{steps}: Flow={flow:.2f} L/min, "
            f"Return={return_flow:.2f} L/min, Press={pressure:.2f} bar"
        )
        time.sleep(2.0)


def emit_cip_alarms(batch_name: str = "M3CIP_R708"):
    """Emit CIP cavitation alarms 2 s apart."""
    print(f"\n[SIMULATOR] Emitting CIP cavitation alarms for batch {batch_name} ...")

    emit_alarm(
        area="Mixer3",
        subsystem="M3CIP8",
        tag="30-FIC-9031",
        event="30-FIC-9031 PV - Low alarm limit violated",
        batch_name=batch_name,
        severity="CRITICAL",
        source="PCL/Mixer3/M3CIP8/CIP",
        telemetry_context={
            "current_flow_lpm": 0.95,
            "low_alarm_limit_lpm": 1.5,
            "supply_pressure_bar": 0.92,
        },
    )

    print("  ... waiting 2 s before second alarm ...")
    time.sleep(2)

    emit_alarm(
        area="Mixer3",
        subsystem="M3CIP8",
        tag="30-PT-9041",
        event="30-PT-9041 PV - Low warning limit violated",
        batch_name=batch_name,
        severity="HIGH",
        source="PCL/Mixer3/M3CIP8/CIP",
        alarm_type="Warning",
        telemetry_context={
            "current_pressure_bar": 0.85,
            "low_warning_limit_bar": 1.2,
            "cip_flow_lpm": 0.90,
        },
    )


if __name__ == "__main__":
    stream_degrading_dosing_telemetry()
    emit_dosing_alarms()
