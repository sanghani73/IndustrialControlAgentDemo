import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import datetime, timezone
from config import db

incident_records = [
    # ── SCN-01: Dosing Starvation — Incident 1 ──
    {
        "incident_id": "INC-2026-0847",
        "timestamp": datetime(2026, 9, 28, 14, 22, 10, tzinfo=timezone.utc),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "batch_name": "101279368",
        "trigger_alarms": [
            "37-VS-4520 Water Dosing too slow",
            "37-FT-4502 Limit value (high) for the negative gradient",
        ],
        "tags_involved": ["37-VS-4520", "37-FT-4502"],
        "root_cause_group": "DOSING_STARVATION",
        "narrative": (
            "Dosing starvation event during CHARGEFL phase on batch 101279368. "
            "Flow rate on 37-FT-4502 dropped from 2.8 to 0.45 kg/s over 60 seconds "
            "while valve 37-VS-4520 was commanded to 95%. Root cause identified as "
            "upstream supply pressure drop due to Header-A cavitation. Supply pressure "
            "at 37-PT-4501 had been drifting down from 2.3 bar to 1.4 bar over the "
            "preceding 10 minutes. Operator increased booster pump 37-P-4501 speed from "
            "1400 RPM to 1750 RPM and switched feed line selector to Header-B. Flow "
            "recovered to 2.6 kg/s within 90 seconds. Batch completed with a 4-minute delay."
        ),
        "actions_taken": [
            {"parameter": "37-P-4501 speed", "from_value": "1400 RPM", "to_value": "1750 RPM"},
            {"parameter": "Feed line selector", "from_value": "Header-A", "to_value": "Header-B"},
        ],
        "outcome": "resolved",
        "resolution_time_seconds": 90,
        "sop_applied": "SOP-MIX3-4520-DOSE",
        "operator_notes": "Header-A pressure was already marginal at shift start. Flagged for maintenance.",
    },
    # ── SCN-01: Dosing Starvation — Incident 2 ──
    {
        "incident_id": "INC-2026-0712",
        "timestamp": datetime(2026, 9, 15, 10, 5, 33, tzinfo=timezone.utc),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "batch_name": "101279201",
        "trigger_alarms": [
            "37-VS-4520 Water Dosing too slow",
        ],
        "tags_involved": ["37-VS-4520", "37-FT-4502"],
        "root_cause_group": "DOSING_STARVATION",
        "narrative": (
            "Intermittent dosing slowdown during CHARGEFL phase on batch 101279201. "
            "Flow rate dropped to 0.9 kg/s briefly then partially recovered to 1.5 kg/s "
            "before the alarm triggered. Valve 37-VS-4520 was at 88% open. Operator "
            "increased pump 37-P-4501 from 1400 to 1750 RPM which restored full flow "
            "to 2.7 kg/s. Supply pressure was borderline at 2.0 bar. Header switch was "
            "not required. Batch completed with 2-minute delay."
        ),
        "actions_taken": [
            {"parameter": "37-P-4501 speed", "from_value": "1400 RPM", "to_value": "1750 RPM"},
        ],
        "outcome": "resolved",
        "resolution_time_seconds": 120,
        "sop_applied": "SOP-MIX3-4520-DOSE",
        "operator_notes": None,
    },
    # ── SCN-02: Thermal Excursion — Incident 1 ──
    {
        "incident_id": "INC-2026-0933",
        "timestamp": datetime(2026, 10, 2, 16, 44, 18, tzinfo=timezone.utc),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "batch_name": "101279502",
        "trigger_alarms": [
            "37-TT-4521 PV - High alarm limit violated",
            "37-TCV-4521 Rbk - Low warning limit violated",
        ],
        "tags_involved": ["37-TT-4521", "37-TCV-4521"],
        "root_cause_group": "THERMAL_EXCURSION",
        "narrative": (
            "Exothermic runaway during HEATCOOL phase on batch 101279502. Process "
            "temperature 37-TT-4521 spiked from 72°C to 93°C in under 3 minutes. "
            "Jacket cooling valve 37-TCV-4521 readback showed only 12% despite a "
            "setpoint of 60%, indicating actuator fault. Operator immediately set "
            "TCV-4521 to 85% cooling mode, increased agitator speed by 20 RPM, and "
            "shut off steam valve 37-SV-4510. Temperature stabilized at 82°C within "
            "2 minutes and gradually returned to 70°C. Instrument technician found "
            "the TCV positioner had a loose feedback linkage."
        ),
        "actions_taken": [
            {"parameter": "37-TCV-4521 position", "from_value": "12%", "to_value": "85%"},
            {"parameter": "Agitator speed", "from_value": "120 RPM", "to_value": "140 RPM"},
            {"parameter": "37-SV-4510 steam valve", "from_value": "40%", "to_value": "0%"},
        ],
        "outcome": "resolved",
        "resolution_time_seconds": 130,
        "sop_applied": "SOP-MIX3-4521-THERM",
        "operator_notes": "TCV positioner linkage was loose. Instrument tech tightened on next shift.",
    },
    # ── SCN-02: Thermal Excursion — Incident 2 ──
    {
        "incident_id": "INC-2026-0811",
        "timestamp": datetime(2026, 9, 22, 8, 15, 45, tzinfo=timezone.utc),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "batch_name": "101279310",
        "trigger_alarms": [
            "37-TT-4521 PV - High alarm limit violated",
        ],
        "tags_involved": ["37-TT-4521", "37-TCV-4521", "37-SV-4510"],
        "root_cause_group": "THERMAL_EXCURSION",
        "narrative": (
            "Temperature excursion during heating-to-cooling transition on batch "
            "101279310. Steam valve 37-SV-4510 did not close promptly when the recipe "
            "transitioned from HEAT to COOL phase, allowing continued energy input while "
            "the jacket was switching to cooling water. Temperature peaked at 88°C. "
            "Operator manually forced steam valve to 0% and set cooling valve to 85%. "
            "Agitator speed was increased by 20 RPM. Temperature returned to setpoint "
            "within 100 seconds."
        ),
        "actions_taken": [
            {"parameter": "37-SV-4510 steam valve", "from_value": "35%", "to_value": "0%"},
            {"parameter": "37-TCV-4521 position", "from_value": "20%", "to_value": "85%"},
            {"parameter": "Agitator speed", "from_value": "110 RPM", "to_value": "130 RPM"},
        ],
        "outcome": "resolved",
        "resolution_time_seconds": 100,
        "sop_applied": "SOP-MIX3-4521-THERM",
        "operator_notes": "Phase transition timing issue in recipe. Raised change request to add 5s delay.",
    },
    # ── SCN-03: CIP Cavitation — Incident 1 ──
    {
        "incident_id": "INC-2026-0905",
        "timestamp": datetime(2026, 10, 5, 13, 10, 22, tzinfo=timezone.utc),
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "batch_name": "101279691",
        "trigger_alarms": [
            "30-FIC-9031 PV - Low alarm limit violated",
            "30-PT-9041 PV - Low warning limit violated",
        ],
        "tags_involved": ["30-FIC-9031", "30-PT-9041"],
        "root_cause_group": "CIP_CAVITATION",
        "narrative": (
            "CIP loop 8 cavitation during caustic wash cycle on batch 101279691. "
            "Flow rate on 30-FIC-9031 dropped from 8.5 to 1.2 m³/h and return pressure "
            "on 30-PT-9041 fell from 2.1 to 0.3 bar. Audible cavitation noise reported "
            "by floor operator. Root cause was air entrainment from a low CIP supply tank "
            "level combined with a partially clogged suction strainer. Operator increased "
            "pump drive frequency by 8 Hz and opened return valve from 30% to 55%. Flow "
            "recovered to 6.8 m³/h within 45 seconds. CIP cycle completed but was extended "
            "by 10 minutes to compensate for the interrupted wash."
        ),
        "actions_taken": [
            {"parameter": "30-P-9031 drive frequency", "from_value": "42 Hz", "to_value": "50 Hz"},
            {"parameter": "30-FIC-9031 valve position", "from_value": "30%", "to_value": "55%"},
        ],
        "outcome": "resolved",
        "resolution_time_seconds": 45,
        "sop_applied": "SOP-MIX3-9031-CIP",
        "operator_notes": "CIP tank was below 20%. Requested tank refill before next cycle.",
    },
    # ── SCN-03: CIP Cavitation — Incident 2 ──
    {
        "incident_id": "INC-2026-0778",
        "timestamp": datetime(2026, 9, 18, 22, 30, 5, tzinfo=timezone.utc),
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "batch_name": "M3CIP_R708",
        "trigger_alarms": [
            "30-FIC-9031 PV - Low alarm limit violated",
        ],
        "tags_involved": ["30-FIC-9031", "30-FT-9041"],
        "root_cause_group": "CIP_CAVITATION",
        "narrative": (
            "Brief CIP supply flow drop during rinse cycle on batch M3CIP_R708. "
            "Flow controller 30-FIC-9031 dropped to 1.8 m³/h for approximately 20 seconds "
            "then partially recovered. Pump drive frequency was increased by 8 Hz per SOP "
            "and valve opened to 55%. Full flow restored to 7.2 m³/h in 60 seconds. "
            "Return pressure on 30-PT-9041 dipped briefly to 0.6 bar but did not trigger "
            "its alarm. Suspected transient air slug in supply line."
        ),
        "actions_taken": [
            {"parameter": "30-P-9031 drive frequency", "from_value": "40 Hz", "to_value": "48 Hz"},
            {"parameter": "30-FIC-9031 valve position", "from_value": "30%", "to_value": "55%"},
        ],
        "outcome": "resolved",
        "resolution_time_seconds": 60,
        "sop_applied": "SOP-MIX3-9031-CIP",
        "operator_notes": "Suspected air slug. No follow-up action required.",
    },
]


def seed_incidents():
    db.incident_history.delete_many({})
    result = db.incident_history.insert_many(incident_records)
    print(f"  -> Seeded {len(result.inserted_ids)} incident records into 'incident_history'.")


if __name__ == "__main__":
    seed_incidents()
