"""End-to-end scenario runner for the manufacturing agent demo.

Usage:
    python -m simulate.simulate_scenario --scenario scn-01
    python -m simulate.simulate_scenario --scenario all
"""

import argparse
import time
from datetime import datetime, timezone

from config import db
from simulate.simulate_telemetry import (
    stream_degrading_dosing_telemetry,
    emit_dosing_alarms,
    stream_thermal_excursion_telemetry,
    emit_thermal_alarms,
    stream_cip_cavitation_telemetry,
    emit_cip_alarms,
)


# Quiet window after streaming telemetry but before firing the hard-threshold
# alarms. Gives Agent 2 time to poll the time-series, see the trend, and emit
# its predictive warning before the control system's trip arrives.
PREDICTIVE_HEAD_START_SECONDS = 10


def _predictive_pause():
    print(
        f"\n[SIMULATOR] Pausing {PREDICTIVE_HEAD_START_SECONDS}s for trend agent "
        f"to inspect sensor_telemetry before hard-threshold trip ..."
    )
    time.sleep(PREDICTIVE_HEAD_START_SECONDS)


def _upsert_production_actual(
    batch_name: str,
    area: str,
    phase: str,
    progress_pct: float = 72.5,
):
    """Create or update a production_actuals record for the batch."""
    db.production_actuals.update_one(
        {"batch_name": batch_name},
        {
            "$set": {
                "batch_name": batch_name,
                "area": area,
                "actual_start": datetime.now(timezone.utc),
                "actual_end": None,
                "current_phase": phase,
                "phase_progress_pct": progress_pct,
                "status": "running",
                "actual_output_kg": None,
                "deviation_from_plan_minutes": 0,
                "last_updated": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"delays": []},
        },
        upsert=True,
    )
    print(f"  [PROD] production_actuals upserted for batch {batch_name}")


# ---------------------------------------------------------------------------
# Scenario runners
# ---------------------------------------------------------------------------

def run_scn_01():
    """SCN-01: Dosing Starvation & Negative Flow Gradient."""
    print("\n" + "=" * 70)
    print("  SCN-01: Dosing Starvation & Negative Flow Gradient")
    print("  Subsystem: M3MX3/CHARGEFL  |  Batch: 101279692")
    print("=" * 70)

    _upsert_production_actual("101279692", "Mixer3", "CHARGEFL", 72.5)
    stream_degrading_dosing_telemetry(batch_name="101279692", steps=12)
    _predictive_pause()
    emit_dosing_alarms(batch_name="101279692")

    print("\n[SCN-01 COMPLETE] Alarms emitted — agents should now correlate and respond.")


def run_scn_02():
    """SCN-02: Thermal Excursion & Valve Actuator Lag."""
    print("\n" + "=" * 70)
    print("  SCN-02: Thermal Excursion & Valve Actuator Lag")
    print("  Subsystem: M3MX3/HEATCOOL  |  Batch: 101279692")
    print("=" * 70)

    _upsert_production_actual("101279692", "Mixer3", "HEATCOOL", 45.0)
    stream_thermal_excursion_telemetry(batch_name="101279692", steps=12)
    _predictive_pause()
    emit_thermal_alarms(batch_name="101279692")

    print("\n[SCN-02 COMPLETE] Alarms emitted — agents should now correlate and respond.")


def run_scn_03():
    """SCN-03: CIP Loop Cavitation & Starvation."""
    print("\n" + "=" * 70)
    print("  SCN-03: CIP Loop Cavitation & Starvation")
    print("  Subsystem: M3CIP8  |  Batch: M3CIP_R708")
    print("=" * 70)

    _upsert_production_actual("M3CIP_R708", "Mixer3", "CIP", 30.0)
    stream_cip_cavitation_telemetry(batch_name="M3CIP_R708", steps=10)
    _predictive_pause()
    emit_cip_alarms(batch_name="M3CIP_R708")

    print("\n[SCN-03 COMPLETE] Alarms emitted — agents should now correlate and respond.")


SCENARIOS = {
    "scn-01": run_scn_01,
    "scn-02": run_scn_02,
    "scn-03": run_scn_03,
}


def main():
    parser = argparse.ArgumentParser(
        description="Simulate plant failure scenarios for the manufacturing agent demo."
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()) + ["all"],
        required=True,
        help="Which failure scenario to simulate (or 'all').",
    )
    args = parser.parse_args()

    if args.scenario == "all":
        for name, runner in SCENARIOS.items():
            runner()
    else:
        SCENARIOS[args.scenario]()

    print("\n" + "=" * 70)
    print("  SIMULATION FINISHED")
    print("=" * 70)


if __name__ == "__main__":
    main()
