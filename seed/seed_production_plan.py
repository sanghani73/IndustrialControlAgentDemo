import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime, timedelta, timezone
from config import db


def _build_production_plan():
    """Build a production plan anchored to the current time so the demo
    is always realistic regardless of when it runs.

    Layout (relative to seed time):
      Shift:    now-30min  ..  now+11.5h
      Batch 1:  now-15min  ..  now+2h15m   (in_progress, started 15 min ago)
      Batch 2:  now+2h30m  ..  now+5h      (pending, comfortably in future)
      CIP:      now+5h15m  ..  now+6h45m   (pending, well in future)
    """
    now = datetime.now(timezone.utc)

    shift_start = now - timedelta(minutes=30)
    shift_end = shift_start + timedelta(hours=12)

    b1_start = now - timedelta(minutes=15)
    b1_end = b1_start + timedelta(minutes=150)

    b2_start = b1_end + timedelta(minutes=15)
    b2_end = b2_start + timedelta(minutes=150)

    cip_start = b2_end + timedelta(minutes=15)
    cip_end = cip_start + timedelta(minutes=90)

    plan_week = now.strftime("%Y-W%W")

    plan = {
        "plan_id": f"PLAN-{plan_week}-MIX3",
        "shift": f"{shift_start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{shift_end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "area": "Mixer3",
        "planned_batches": [
            {
                "batch_name": "101279692",
                "recipe": "RECIPE-CHARGEFL-A",
                "planned_start": b1_start,
                "planned_end": b1_end,
                "planned_duration_minutes": 150,
                "status": "in_progress",
                "material_requirements": [
                    {"material": "Water-Demin", "quantity_kg": 2500, "source_tank": "TK-RM-01"},
                    {"material": "Solvent-A", "quantity_kg": 800, "source_tank": "TK-RM-03"},
                ],
            },
            {
                "batch_name": "101279693",
                "recipe": "RECIPE-CHARGEFL-B",
                "planned_start": b2_start,
                "planned_end": b2_end,
                "planned_duration_minutes": 150,
                "status": "pending",
                "material_requirements": [
                    {"material": "Water-Demin", "quantity_kg": 2500, "source_tank": "TK-RM-01"},
                    {"material": "Solvent-B", "quantity_kg": 600, "source_tank": "TK-RM-04"},
                ],
            },
            {
                "batch_name": "CIP-MIX3-R709",
                "recipe": "CIP-FULL",
                "planned_start": cip_start,
                "planned_end": cip_end,
                "planned_duration_minutes": 90,
                "status": "pending",
                "material_requirements": [
                    {"material": "CIP-Caustic", "quantity_kg": 150, "source_tank": "TK-CIP-01"},
                ],
            },
        ],
        "shift_kpis": {
            "target_batches": 2,
            "target_output_kg": 6400,
            "cip_cycles_planned": 1,
        },
    }

    actual = {
        "batch_name": "101279692",
        "area": "Mixer3",
        "actual_start": b1_start + timedelta(minutes=3),
        "actual_end": None,
        "current_phase": "CHARGEFL",
        "phase_progress_pct": 8.0,
        "status": "running",
        "delays": [],
        "actual_output_kg": None,
        "deviation_from_plan_minutes": 3,
        "last_updated": now,
    }

    return plan, actual


automation_policy_records = [
    {
        "policy_id": "POL-VALVE-SMALL",
        "action_type": "valve_position_override",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "approval_mode": "autonomous",
        "description": "Small valve adjustments (<5% delta) can execute without approval",
        "max_auto_delta_pct": 5.0,
        "escalation_threshold": "HIGH",
    },
    {
        "policy_id": "POL-VALVE-LARGE",
        "action_type": "valve_position_override_large",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "approval_mode": "human_approval",
        "description": "Large valve overrides (>=5% delta) require operator confirmation",
        "max_auto_delta_pct": None,
        "escalation_threshold": "CRITICAL",
    },
    {
        "policy_id": "POL-PUMP-SPEED",
        "action_type": "pump_speed_change",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "approval_mode": "human_approval",
        "description": "Pump speed changes require operator confirmation",
        "max_auto_delta_pct": None,
        "escalation_threshold": "HIGH",
    },
    {
        "policy_id": "POL-AGITATOR",
        "action_type": "agitator_speed_change",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "approval_mode": "autonomous",
        "description": (
            "Agitator speed trims (e.g. +/- 20 RPM) are routine process-stability "
            "actions that can execute without operator approval."
        ),
        "max_auto_delta_pct": 25.0,
        "escalation_threshold": "HIGH",
    },
    {
        "policy_id": "POL-STEAM-SHUTOFF",
        "action_type": "steam_shutoff",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "approval_mode": "autonomous",
        "description": "Emergency steam shutoff executes immediately for safety",
        "max_auto_delta_pct": None,
        "escalation_threshold": "CRITICAL",
    },
    {
        "policy_id": "POL-CIP-PUMP",
        "action_type": "pump_frequency_change",
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "approval_mode": "human_approval",
        "description": "CIP pump frequency changes require operator confirmation",
        "max_auto_delta_pct": None,
        "escalation_threshold": "HIGH",
    },
]


def seed_production_plan():
    plan, actual = _build_production_plan()

    db.production_plans.delete_many({})
    db.production_plans.insert_one(plan)
    print("  -> Seeded 1 production plan into 'production_plans'.")

    db.automation_policies.delete_many({})
    result = db.automation_policies.insert_many(automation_policy_records)
    print(f"  -> Seeded {len(result.inserted_ids)} automation policies into 'automation_policies'.")

    db.production_actuals.delete_many({})
    db.production_actuals.insert_one(actual)
    print("  -> Seeded 1 production actual into 'production_actuals'.")


if __name__ == "__main__":
    seed_production_plan()
