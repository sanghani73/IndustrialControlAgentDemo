import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import db

alarm_definition_records = [
    # ── SCN-01: DOSING_STARVATION ──
    {
        "alarm_code": "ALM-DOSE-SLOW",
        "event_pattern": "Water Dosing too slow",
        "description": (
            "Flow rate during coarse dosing phase has fallen below the minimum threshold "
            "of 1.2 kg/s. Typically indicates upstream water supply pressure drop caused by "
            "cavitation in the header, a partially closed isolation valve, or booster pump "
            "degradation. Often accompanied by negative flow gradient and weigh error alarms."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-VS-4520",
        "severity_default": "CRITICAL",
        "related_alarm_codes": ["ALM-DOSE-GRADIENT", "ALM-DOSE-WEIGHT"],
        "root_cause_group": "DOSING_STARVATION",
        "linked_sop_ids": ["SOP-MIX3-4520-DOSE"],
        "operator_guidance": "Check upstream supply pressure at 37-PT-4501 and valve position of 37-VS-4520 before escalating.",
    },
    {
        "alarm_code": "ALM-DOSE-GRADIENT",
        "event_pattern": "Limit value (high) for the negative gradient",
        "description": (
            "Rate-of-change limit on flow transmitter 37-FT-4502 has been exceeded in the "
            "negative direction, indicating a rapid decline in water dosing flow rate. "
            "This gradient alarm precedes full starvation and suggests an evolving supply "
            "line blockage or pump trip rather than a steady-state low-flow condition."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-FT-4502",
        "severity_default": "HIGH",
        "related_alarm_codes": ["ALM-DOSE-SLOW", "ALM-DOSE-WEIGHT"],
        "root_cause_group": "DOSING_STARVATION",
        "linked_sop_ids": ["SOP-MIX3-4520-DOSE"],
        "operator_guidance": "Confirm flow trend on 37-FT-4502; if gradient persists, check pump 37-P-4501 status.",
    },
    {
        "alarm_code": "ALM-DOSE-WEIGHT",
        "event_pattern": "Water Dosing Weigh Error",
        "description": (
            "Tank weight accumulation on 37-WT-4521 has deviated from the expected dosing "
            "profile during the CHARGEFL recipe phase. The actual weight gain is significantly "
            "lower than the recipe target rate, confirming that insufficient material is being "
            "delivered to the vessel."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-WT-4521",
        "severity_default": "HIGH",
        "related_alarm_codes": ["ALM-DOSE-SLOW", "ALM-DOSE-GRADIENT"],
        "root_cause_group": "DOSING_STARVATION",
        "linked_sop_ids": ["SOP-MIX3-4520-DOSE"],
        "operator_guidance": "Cross-check weight trend against flow rate. If both are declining, root cause is upstream.",
    },
    # ── SCN-02: THERMAL_EXCURSION ──
    {
        "alarm_code": "ALM-THERM-HIGH",
        "event_pattern": "37-TT-4521 PV - High alarm limit violated",
        "description": (
            "Process temperature in Mixer3 main vessel has exceeded the high alarm limit, "
            "indicating an exothermic runaway condition. The reaction temperature is rising "
            "faster than the jacket cooling system can compensate. Immediate cooling intervention "
            "and possible steam shutoff are required to prevent product degradation or vessel overpressure."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-TT-4521",
        "severity_default": "CRITICAL",
        "related_alarm_codes": ["ALM-TCV-READBACK"],
        "root_cause_group": "THERMAL_EXCURSION",
        "linked_sop_ids": ["SOP-MIX3-4521-THERM"],
        "operator_guidance": "Immediately verify TCV-4521 position and confirm cooling water is flowing through jacket.",
    },
    {
        "alarm_code": "ALM-TCV-READBACK",
        "event_pattern": "37-TCV-4521 Rbk - Low warning limit violated",
        "description": (
            "Readback from jacket temperature control valve 37-TCV-4521 is below the low "
            "warning limit, meaning the valve actuator is not reaching its commanded position. "
            "This indicates either actuator mechanical fault, air supply failure, or positioner "
            "calibration drift. In a heating phase, this starves the jacket of cooling capacity."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-TCV-4521",
        "severity_default": "HIGH",
        "related_alarm_codes": ["ALM-THERM-HIGH"],
        "root_cause_group": "THERMAL_EXCURSION",
        "linked_sop_ids": ["SOP-MIX3-4521-THERM"],
        "operator_guidance": "Compare TCV setpoint vs readback; check instrument air supply and actuator linkage.",
    },
    # ── SCN-03: CIP_CAVITATION ──
    {
        "alarm_code": "ALM-CIP-FLOW-LOW",
        "event_pattern": "30-FIC-9031 PV - Low alarm limit violated",
        "description": (
            "CIP supply loop flow rate measured by 30-FIC-9031 has dropped below the low "
            "alarm limit, indicating insufficient cleaning solution flow through the vessel "
            "spray devices. Common causes include CIP tank level depletion, pump cavitation "
            "due to air entrainment, or a blockage in the supply manifold."
        ),
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "equipment_tag": "30-FIC-9031",
        "severity_default": "CRITICAL",
        "related_alarm_codes": ["ALM-CIP-PRESS-LOW"],
        "root_cause_group": "CIP_CAVITATION",
        "linked_sop_ids": ["SOP-MIX3-9031-CIP"],
        "operator_guidance": "Check CIP tank level and pump suction pressure. Listen for cavitation noise at pump.",
    },
    {
        "alarm_code": "ALM-CIP-PRESS-LOW",
        "event_pattern": "30-PT-9041 PV - Low warning limit violated",
        "description": (
            "Return line pressure on CIP loop 8 has fallen below the low warning limit, "
            "suggesting the return pump is struggling to maintain circulation. Combined with "
            "a low supply flow, this points to cavitation or air lock in the CIP circuit. "
            "Continued operation risks incomplete cleaning and product contamination in the next batch."
        ),
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "equipment_tag": "30-PT-9041",
        "severity_default": "HIGH",
        "related_alarm_codes": ["ALM-CIP-FLOW-LOW"],
        "root_cause_group": "CIP_CAVITATION",
        "linked_sop_ids": ["SOP-MIX3-9031-CIP"],
        "operator_guidance": "Verify return line is not blocked; check pump inlet for air pockets.",
    },
    # ── Predictive (Agent 2) alarm definitions ──
    # Emitted by the trend agent when a rolling derivative over sensor_telemetry
    # projects an imminent breach. They share root_cause_group with the hard
    # trip alarms so the correlator folds the predictive warning and the
    # subsequent trip into the same remediation flow.
    {
        "alarm_code": "ALM-DOSE-SLOPE-NEG",
        "event_pattern": "PREDICTIVE: Dosing flow slope negative",
        "description": (
            "Rolling derivative over sensor_telemetry shows the dosing flow rate on "
            "37-FT-4502 is declining faster than the recovery setpoint rate. Projected "
            "to breach the low-flow threshold before the control system's threshold alarm "
            "fires. This is an early-warning event emitted by the trend-analysis agent."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-FT-4502",
        "severity_default": "WARNING",
        "related_alarm_codes": ["ALM-DOSE-SLOW", "ALM-DOSE-GRADIENT"],
        "root_cause_group": "DOSING_STARVATION",
        "linked_sop_ids": ["SOP-MIX3-4520-DOSE"],
        "operator_guidance": "Pre-check supply pressure and pump; operator has head start before trip.",
    },
    {
        "alarm_code": "ALM-THERM-SLOPE-POS",
        "event_pattern": "PREDICTIVE: Vessel temperature slope rising",
        "description": (
            "Rolling derivative over sensor_telemetry shows the Mixer3 vessel temperature "
            "on 37-TT-4521 is climbing at a rate the jacket cooling cannot keep pace with. "
            "Projected to breach the high-temperature alarm limit before the control "
            "system fires its hard trip. Early-warning event from the trend-analysis agent."
        ),
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "equipment_tag": "37-TT-4521",
        "severity_default": "WARNING",
        "related_alarm_codes": ["ALM-THERM-HIGH", "ALM-TCV-READBACK"],
        "root_cause_group": "THERMAL_EXCURSION",
        "linked_sop_ids": ["SOP-MIX3-4521-THERM"],
        "operator_guidance": "Pre-stage cooling response; operator has head start before trip.",
    },
    {
        "alarm_code": "ALM-CIP-SLOPE-NEG",
        "event_pattern": "PREDICTIVE: CIP supply pressure slope dropping",
        "description": (
            "Rolling derivative over sensor_telemetry shows the CIP loop supply pressure "
            "on 30-PT-9041 is dropping at a rate consistent with air entrainment or "
            "cavitation onset. Projected to breach the low-pressure warning before the "
            "control system fires its hard trip. Early-warning event from the trend agent."
        ),
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "equipment_tag": "30-PT-9041",
        "severity_default": "WARNING",
        "related_alarm_codes": ["ALM-CIP-FLOW-LOW", "ALM-CIP-PRESS-LOW"],
        "root_cause_group": "CIP_CAVITATION",
        "linked_sop_ids": ["SOP-MIX3-9031-CIP"],
        "operator_guidance": "Pre-check CIP tank level and pump suction; operator has head start.",
    },
]


def seed_alarm_definitions():
    db.alarm_definitions.delete_many({})
    result = db.alarm_definitions.insert_many(alarm_definition_records)
    print(f"  -> Seeded {len(result.inserted_ids)} alarm definitions into 'alarm_definitions'.")


if __name__ == "__main__":
    seed_alarm_definitions()
