import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import db

sop_records = [
    {
        "sop_id": "SOP-MIX3-4520-DOSE",
        "title": "Mixer3 Main Vessel Water and Solvent Dosing Starvation",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "applicable_tags": ["37-VS-4520", "37-FT-4502", "37-WT-4521"],
        "linked_alarm_codes": ["ALM-DOSE-SLOW", "ALM-DOSE-GRADIENT", "ALM-DOSE-WEIGHT"],
        "linked_equipment_ids": ["EQ-37-VS-4520", "EQ-37-FT-4502", "EQ-37-WT-4521"],
        "content": (
            "Standard Operating Procedure for dosing delivery rate faults. "
            "Applies to alarms: 'Water Dosing too slow', 'Limit value (high) for the negative gradient', "
            "and 'Water Dosing Weigh Error'. "
            "Corrective Procedures: "
            "1. If flow rate 37-FT-4502 falls below 1.2 kg/s during coarse dosing, override valve "
            "37-VS-4520 position setpoint by +12%. "
            "2. Command supply line booster pump 37-P-4501 speed setpoint up from 1400 RPM to 1750 RPM. "
            "3. If delivery pressure 37-PT-4501 remains below 2.0 bar, switch feed line selector to Header-B."
        ),
    },
    {
        "sop_id": "SOP-MIX3-4521-THERM",
        "title": "Main Vessel Exothermic Overheating and TCV Readback Fault",
        "area": "Mixer3",
        "subsystem": "M3MX3",
        "applicable_tags": ["37-TT-4521", "37-TCV-4521", "37-CM-4590"],
        "linked_alarm_codes": ["ALM-THERM-HIGH", "ALM-TCV-READBACK"],
        "linked_equipment_ids": ["EQ-37-TT-4521", "EQ-37-TCV-4521", "EQ-37-CM-4590"],
        "content": (
            "Standard Operating Procedure for batch thermal runaway. "
            "Applies to: '37-TT-4521 PV - High alarm limit violated' and "
            "'37-TCV-4521 Rbk - Low warning limit violated'. "
            "Corrective Procedures: "
            "1. Set jacket cooling control valve 37-TCV-4521 position setpoint to 85% cooling mode. "
            "2. Increment main mixer agitator speed setpoint by +20 RPM to ensure uniform heat transfer. "
            "3. Cut off steam inlet valve 37-SV-4510 setpoint to 0% immediately."
        ),
    },
    {
        "sop_id": "SOP-MIX3-9031-CIP",
        "title": "CIP Loop Flow Rate Starvation and Supply Cavitation",
        "area": "Mixer3",
        "subsystem": "M3CIP8",
        "applicable_tags": ["30-FIC-9031", "30-FT-9041", "30-PT-9041"],
        "linked_alarm_codes": ["ALM-CIP-FLOW-LOW", "ALM-CIP-PRESS-LOW"],
        "linked_equipment_ids": ["EQ-30-FIC-9031", "EQ-30-FT-9041", "EQ-30-PT-9041"],
        "content": (
            "Standard Operating Procedure for CIP return cavitation. "
            "Applies to: '30-FIC-9031 PV - Low alarm limit violated' and "
            "'30-PT-9041 PV - Low warning limit violated'. "
            "Corrective Procedures: "
            "1. Step CIP booster pump drive frequency setpoint up by +8 Hz. "
            "2. Override return valve 30-FIC-9031 actuator position setpoint from 30% to 55%."
        ),
    },
    # --- Noise SOPs: realistic plant procedures unrelated to the 3 demo scenarios ---
    # These test that the vector search picks the right SOP from a realistic library,
    # not just the only option. A real plant maintains hundreds of these.
    {
        "sop_id": "SOP-UTIL-2210-AIR",
        "title": "Instrument Air Header Low Pressure and Dryer Dew Point High",
        "area": "Utilities",
        "subsystem": "AIR",
        "applicable_tags": ["22-PT-2210", "22-DP-2215"],
        "linked_alarm_codes": ["ALM-IA-PRESS-LOW", "ALM-IA-DEWPOINT-HIGH"],
        "linked_equipment_ids": ["EQ-22-PT-2210", "EQ-22-DP-2215"],
        "content": (
            "Standard Operating Procedure for compressed instrument-air system faults. "
            "Applies to: '22-PT-2210 PV - Low alarm limit violated' (header pressure below 5.5 bar) "
            "and '22-DP-2215 PV - High warning limit violated' (dew point above -20 degC). "
            "Loss of instrument air drives pneumatic actuators to their fail-safe position. "
            "Corrective Procedures: "
            "1. Confirm standby compressor 22-K-2211 is in AUTO and bring it online if lead unit has tripped. "
            "2. Switch dryer train from Dryer-A to Dryer-B via 22-XV-2214; initiate regeneration cycle on offline unit. "
            "3. Isolate non-critical air users (plant yard, workshop drops) via 22-XV-2290."
        ),
    },
    {
        "sop_id": "SOP-UTIL-6102-CHW",
        "title": "Chilled Water System Low Approach Temperature and Chiller Trip",
        "area": "Utilities",
        "subsystem": "CHW",
        "applicable_tags": ["61-TT-6102", "61-TT-6103", "61-FT-6110"],
        "linked_alarm_codes": ["ALM-CHW-APPROACH-LOW", "ALM-CHILLER-TRIP"],
        "linked_equipment_ids": ["EQ-61-TT-6102", "EQ-61-TT-6103"],
        "content": (
            "Standard Operating Procedure for chilled water plant deviations. "
            "Applies to: '61-TT-6102 PV - Approach temperature low' (supply/return delta narrowing) "
            "and 'Chiller 61-CH-6101 trip on condenser high-pressure cutout'. "
            "This is a utility-side cooling fault and does not apply to reactor jacket temperature control. "
            "Corrective Procedures: "
            "1. Bring standby chiller 61-CH-6102 online in cascade mode; stage condenser water pumps. "
            "2. If approach is narrowing due to fouling, schedule condenser-tube cleaning via maintenance work order. "
            "3. Reduce non-critical chilled water load by sequencing air-handler VSDs down by 10 Hz."
        ),
    },
    {
        "sop_id": "SOP-BOIL-4420-FW",
        "title": "Boiler Feedwater Conductivity High and Blowdown Sequence",
        "area": "Utilities",
        "subsystem": "BOIL",
        "applicable_tags": ["44-CND-4420", "44-LT-4421"],
        "linked_alarm_codes": ["ALM-BFW-COND-HIGH", "ALM-BLR-DRUM-LOW"],
        "linked_equipment_ids": ["EQ-44-CND-4420", "EQ-44-LT-4421"],
        "content": (
            "Standard Operating Procedure for steam-boiler water chemistry faults. "
            "Applies to: '44-CND-4420 PV - Conductivity above 180 uS/cm' and drum-level deviations following blowdown. "
            "Corrective Procedures: "
            "1. Open continuous blowdown valve 44-BDV-4420 incrementally to 25% until conductivity trends below 150 uS/cm. "
            "2. Sample feedwater at 44-SP-4420 and send to lab for silica and hardness analysis. "
            "3. If silica carryover is suspected, initiate manual bottom blowdown per water-treatment specialist directive."
        ),
    },
    {
        "sop_id": "SOP-DUST-5501-ATEX",
        "title": "Dust Collector Differential Pressure High (ATEX Zone 22)",
        "area": "Powder-Handling",
        "subsystem": "DUST",
        "applicable_tags": ["55-DPT-5501", "55-RPM-5505"],
        "linked_alarm_codes": ["ALM-DUST-DP-HIGH", "ALM-DUST-ROTVALVE-SLOW"],
        "linked_equipment_ids": ["EQ-55-DPT-5501", "EQ-55-RPM-5505"],
        "content": (
            "Standard Operating Procedure for baghouse differential-pressure excursions in ATEX Zone 22. "
            "Applies to: '55-DPT-5501 PV - DP above 2.5 kPa' indicating bag blinding or filter saturation. "
            "Risk: dust accumulation increases explosion hazard; LEL may be approached. "
            "Corrective Procedures: "
            "1. Initiate reverse-pulse cleaning cycle on 55-DC-5501; verify solenoid firing sequence 1-through-8. "
            "2. Confirm rotary airlock 55-RV-5503 is turning at nameplate 22 RPM; investigate if drive has slipped. "
            "3. If DP does not recover within 10 minutes, stop upstream powder transfer and schedule bag replacement."
        ),
    },
    {
        "sop_id": "SOP-CENT-7701-VIB",
        "title": "Decanter Centrifuge High Vibration and Bowl Imbalance Trip",
        "area": "Separation",
        "subsystem": "CENT",
        "applicable_tags": ["77-VIB-7701", "77-TT-7702"],
        "linked_alarm_codes": ["ALM-CENT-VIB-HIGH", "ALM-CENT-BRG-TEMP"],
        "linked_equipment_ids": ["EQ-77-VIB-7701", "EQ-77-TT-7702"],
        "content": (
            "Standard Operating Procedure for solid-bowl centrifuge mechanical faults. "
            "Applies to: '77-VIB-7701 PV - Vibration above 11 mm/s RMS' and bearing-temperature trending. "
            "Corrective Procedures: "
            "1. Trip centrifuge drive via 77-HS-7701 and allow controlled coastdown; do NOT apply brake. "
            "2. Verify feed stream solids content is within 2-6% w/w specification; dilute feed if elevated. "
            "3. On restart, ramp bowl speed from 0 to 1800 RPM in 60-second steps and watch 77-VIB-7701 trend."
        ),
    },
    {
        "sop_id": "SOP-N2-3301-INERT",
        "title": "Nitrogen Inerting Header Low Pressure and Vessel Blanket Loss",
        "area": "Utilities",
        "subsystem": "N2",
        "applicable_tags": ["33-PT-3301", "33-FT-3310"],
        "linked_alarm_codes": ["ALM-N2-PRESS-LOW", "ALM-N2-FLOW-SURGE"],
        "linked_equipment_ids": ["EQ-33-PT-3301", "EQ-33-FT-3310"],
        "content": (
            "Standard Operating Procedure for loss of nitrogen inerting across solvent-storage and reactor headspaces. "
            "Applies to: '33-PT-3301 PV - Header pressure below 1.2 barg' and sustained flow surge on 33-FT-3310. "
            "Loss of blanket risks ingress of air into flammable headspace; respond quickly. "
            "Corrective Procedures: "
            "1. Open backup liquid-nitrogen vaporizer 33-VAP-3302 to supplement supply. "
            "2. Identify high-draw user via 33-FT-3310 trend and isolate if non-critical. "
            "3. If pressure stays below 0.8 barg for over 2 minutes, initiate ERP step for solvent-tank purge hold."
        ),
    },
    {
        "sop_id": "SOP-NEUT-8810-PH",
        "title": "Neutralization Pit pH Dosing Failure and Discharge Hold",
        "area": "Effluent",
        "subsystem": "NEUT",
        "applicable_tags": ["88-PH-8810", "88-FIC-8812"],
        "linked_alarm_codes": ["ALM-NEUT-PH-OOR", "ALM-NEUT-DOSE-FAIL"],
        "linked_equipment_ids": ["EQ-88-PH-8810", "EQ-88-FIC-8812"],
        "content": (
            "Standard Operating Procedure for pH control failure on effluent neutralization pit. "
            "Applies to: '88-PH-8810 PV outside 6.5-8.5' and 'caustic dosing pump 88-P-8812 feedback mismatch'. "
            "This is an effluent-side dosing control fault; it is NOT related to reactor charge dosing. "
            "Corrective Procedures: "
            "1. Close discharge valve 88-XV-8820 to hold effluent until pH recovers. "
            "2. Verify dosing-pump stroke counter against flow transmitter 88-FIC-8812; recalibrate if divergence > 5%. "
            "3. Switch to redundant dosing skid 88-P-8813; sample pit for lab verification before reopening discharge."
        ),
    },
    {
        "sop_id": "SOP-HTOIL-9910-TEMP",
        "title": "Hot Oil Heater Outlet Temperature Deviation and Pump Cavitation",
        "area": "Utilities",
        "subsystem": "HTOIL",
        "applicable_tags": ["99-TT-9910", "99-PT-9911"],
        "linked_alarm_codes": ["ALM-HTOIL-TEMP-DEV", "ALM-HTOIL-SUCT-LOW"],
        "linked_equipment_ids": ["EQ-99-TT-9910", "EQ-99-PT-9911"],
        "content": (
            "Standard Operating Procedure for the Therminol thermal-fluid loop supplying crystallizer jackets. "
            "Applies to: '99-TT-9910 PV deviation beyond +/- 8 degC from setpoint' and suction-pressure trending low. "
            "This loop serves crystallizer jackets; it is not the Mixer3 reactor cooling circuit. "
            "Corrective Procedures: "
            "1. Verify burner firing-rate controller on 99-HTR-9910 and bias output by -5% if overshoot pattern. "
            "2. Vent expansion tank 99-ET-9920 if degassing has not run in the last 24 hours. "
            "3. If suction pressure stays low, inspect strainer 99-STR-9910 for carbon fouling."
        ),
    },
    {
        "sop_id": "SOP-UV-4040-LAMP",
        "title": "Water-Treatment UV Sterilizer Lamp Fault and Low-Dose Bypass",
        "area": "Water-Treatment",
        "subsystem": "UV",
        "applicable_tags": ["40-UVI-4040", "40-FT-4041"],
        "linked_alarm_codes": ["ALM-UV-LAMP-FAIL", "ALM-UV-DOSE-LOW"],
        "linked_equipment_ids": ["EQ-40-UVI-4040"],
        "content": (
            "Standard Operating Procedure for the purified-water loop UV sterilizer. "
            "Applies to: '40-UVI-4040 PV - UV intensity below 60% of specification' and dose below 40 mJ/cm2. "
            "Loss of UV disinfection diverts flow to recycle until integrity is restored. "
            "Corrective Procedures: "
            "1. Open recycle valve 40-XV-4049 and close supply valve 40-XV-4042; place loop in recirculation. "
            "2. Replace affected UV lamp cartridges per OEM 40-UV-4040 maintenance checklist. "
            "3. Hold product-water release until two successive conductivity and TOC samples pass specification."
        ),
    },
    {
        "sop_id": "SOP-VFD-5050-TRIP",
        "title": "Utility Pump VFD Overcurrent Trip and Thermal Overload Lockout",
        "area": "Electrical",
        "subsystem": "VFD",
        "applicable_tags": ["50-II-5050", "50-TT-5051"],
        "linked_alarm_codes": ["ALM-VFD-OC-TRIP", "ALM-VFD-TEMP-HIGH"],
        "linked_equipment_ids": ["EQ-50-II-5050"],
        "content": (
            "Standard Operating Procedure for variable-frequency-drive overcurrent trips on 50/51 class utility pumps. "
            "Applies to: '50-II-5050 - Overcurrent trip event' and drive heatsink temperature above 65 degC. "
            "Corrective Procedures: "
            "1. Allow drive 5-minute thermal reset; attempt controlled restart via local HMI only after fan test. "
            "2. Verify downstream pump suction is primed and no cavitation signature on acoustic monitor. "
            "3. If overcurrent repeats, bring in electrical team to measure phase imbalance before further restart attempts."
        ),
    },
    {
        "sop_id": "SOP-TANKF-6600-LEAK",
        "title": "Tank Farm Bund Leak Detection and Containment Response",
        "area": "Tank-Farm",
        "subsystem": "BUND",
        "applicable_tags": ["66-LD-6601", "66-LT-6602"],
        "linked_alarm_codes": ["ALM-BUND-LEAK", "ALM-BUND-LVL-HIGH"],
        "linked_equipment_ids": ["EQ-66-LD-6601", "EQ-66-LT-6602"],
        "content": (
            "Standard Operating Procedure for secondary containment breach in the solvent tank farm. "
            "Applies to: '66-LD-6601 - Hydrocarbon leak detected' and 'bund sump level 66-LT-6602 trending'. "
            "Corrective Procedures: "
            "1. Close inlet and outlet manifolds on affected tank TK-6601 via 66-XV-6610 and 66-XV-6611. "
            "2. Dispatch tank-farm operator to visually inspect bund; initiate vacuum-truck call-off if volume exceeds 500 L. "
            "3. Notify environmental duty officer; log event ID in incident_history for regulatory reporting."
        ),
    },
    {
        "sop_id": "SOP-PACK-7200-WRAP",
        "title": "End-of-Line Palletizer Stretch-Wrapper Film Break and Pallet Reject",
        "area": "Packaging",
        "subsystem": "WRAP",
        "applicable_tags": ["72-PEC-7201", "72-DRV-7202"],
        "linked_alarm_codes": ["ALM-WRAP-FILM-BREAK", "ALM-WRAP-DRV-FAULT"],
        "linked_equipment_ids": ["EQ-72-PEC-7201"],
        "content": (
            "Standard Operating Procedure for end-of-line palletizer stretch-wrapper film breaks. "
            "Applies to: '72-PEC-7201 - Film tension lost' and recurring drive 72-DRV-7202 faults. "
            "Corrective Procedures: "
            "1. Divert affected pallet to manual-wrap station via 72-XV-7290; do not release to warehouse. "
            "2. Reload film carriage and check pre-stretch roller gap against 72-GA-7205 spec sheet. "
            "3. If drive faults repeat, swap to backup wrapper 72-WRP-7220 and raise maintenance ticket."
        ),
    },
]


def seed_sops():
    db.plant_sops.delete_many({})
    result = db.plant_sops.insert_many(sop_records)
    print(f"  -> Seeded {len(result.inserted_ids)} SOP documents into 'plant_sops'.")
    print("  -> Atlas autoEmbed index will automatically vectorize these records via Voyage AI.")


if __name__ == "__main__":
    seed_sops()
