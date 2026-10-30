"""Agent 1 — Enhanced Reactive SOP Matcher

Watches correlated_alarm_groups via Change Stream. For each group:
1. Enriches with equipment context
2. Vector-searches SOPs (Atlas autoEmbed)
3. Retrieves historical incidents (vector + structured)
4. Checks automation policies for approval mode
5. Calls the LLM for a structured remediation plan
6. Writes to action_queue with appropriate status
"""

import json
from datetime import datetime, timezone

from config import LLM_MODEL, llm_client, db

SUBMIT_ACTION_PLAN_TOOL = {
    "name": "submit_action_plan",
    "description": (
        "Submit a structured remediation action plan based on the SOP and alarm context."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sop_id": {"type": "string"},
            "diagnosis": {"type": "string"},
            "severity": {
                "type": "string",
                "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            },
            "setpoint_changes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "parameter": {"type": "string"},
                        "current_value": {"type": "string"},
                        "target_value": {"type": "string"},
                        "unit": {"type": "string"},
                        "sop_reference": {"type": "string"},
                    },
                    "required": [
                        "parameter",
                        "current_value",
                        "target_value",
                        "unit",
                        "sop_reference",
                    ],
                },
            },
            "operational_justification": {"type": "string"},
        },
        "required": [
            "sop_id",
            "diagnosis",
            "severity",
            "setpoint_changes",
            "operational_justification",
        ],
    },
}

SYSTEM_PROMPT = (
    "You are an industrial safety AI agent for a chemical batch mixing plant (Mixer3). "
    "Your role is to diagnose alarm conditions and recommend precise physical setpoint "
    "adjustments strictly grounded in the provided Standard Operating Procedure (SOP).\n\n"
    "Rules:\n"
    "- ONLY recommend actions explicitly specified in the SOP\n"
    "- Reference the specific SOP step number for each setpoint change\n"
    "- Consider historical incident data when assessing urgency and approach\n"
    "- Factor in equipment operating ranges when validating proposed setpoints\n"
    "- If the SOP does not cover the situation, state this clearly and do not invent actions\n\n"
    "Use the submit_action_plan tool to provide your structured response."
)

_action_counter = 0


def _get_equipment_context(tags: list[str]) -> str:
    lines = []
    for tag in tags:
        equip = db.equipment_registry.find_one({"tag": tag})
        if not equip:
            continue
        r = equip.get("normal_operating_range", {})
        lines.append(
            f"- {tag}: {equip['description']} | Type: {equip['equipment_type']} | "
            f"Normal range: {r.get('min')}–{r.get('max')} {r.get('unit', '')} | "
            f"Upstream: {equip.get('upstream_dependencies', [])} | "
            f"Downstream: {equip.get('downstream_dependencies', [])}"
        )
    return "\n".join(lines) if lines else "No equipment data available."


def _search_sop(alarm_text: str, area: str) -> dict | None:
    pipeline = [
        {
            "$vectorSearch": {
                "index": "sop_auto_vector_index",
                "path": "content",
                "query": {"text": alarm_text},
                "numCandidates": 15,
                "limit": 1,
                "filter": {"area": {"$eq": area}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "sop_id": 1,
                "title": 1,
                "content": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]
    results = list(db.plant_sops.aggregate(pipeline))
    return results[0] if results else None


def _get_historical_context(
    alarm_text: str, area: str, root_cause_group: str
) -> list[dict]:
    """Dual retrieval: vector search + structured query, deduplicated."""
    seen = set()
    incidents = []

    # Vector search on incident narratives
    try:
        vs_pipeline = [
            {
                "$vectorSearch": {
                    "index": "incident_auto_vector_index",
                    "path": "narrative",
                    "query": {"text": alarm_text},
                    "numCandidates": 20,
                    "limit": 3,
                    "filter": {"area": {"$eq": area}},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "incident_id": 1,
                    "timestamp": 1,
                    "narrative": 1,
                    "actions_taken": 1,
                    "outcome": 1,
                    "resolution_time_seconds": 1,
                    "operator_notes": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        for inc in db.incident_history.aggregate(vs_pipeline):
            iid = inc["incident_id"]
            if iid not in seen:
                seen.add(iid)
                incidents.append(inc)
    except Exception as e:
        print(f"[AGENT 1] Vector search on incidents failed (index may not exist): {e}")

    # Structured query by root_cause_group
    if root_cause_group and root_cause_group != "UNKNOWN":
        structured = (
            db.incident_history.find(
                {"root_cause_group": root_cause_group, "area": area},
                {
                    "_id": 0,
                    "incident_id": 1,
                    "timestamp": 1,
                    "narrative": 1,
                    "actions_taken": 1,
                    "outcome": 1,
                    "resolution_time_seconds": 1,
                    "operator_notes": 1,
                },
            )
            .sort("timestamp", -1)
            .limit(5)
        )
        for inc in structured:
            iid = inc["incident_id"]
            if iid not in seen:
                seen.add(iid)
                incidents.append(inc)

    return incidents[:3]


def _format_historical_context(incidents: list[dict]) -> str:
    if not incidents:
        return "No similar historical incidents found."

    lines = [f"Found {len(incidents)} similar past incident(s) in this area:\n"]
    for i, inc in enumerate(incidents, 1):
        ts = inc.get("timestamp", "")
        if hasattr(ts, "strftime"):
            ts = ts.strftime("%Y-%m-%d")
        actions = "; ".join(
            f"{a['parameter']}: {a['from_value']} → {a['to_value']}"
            for a in inc.get("actions_taken", [])
        )
        lines.append(
            f"{i}. [{inc['incident_id']}] {ts}\n"
            f"   Actions taken: {actions or 'None recorded'}\n"
            f"   Outcome: {inc.get('outcome', 'unknown')} "
            f"(resolved in {inc.get('resolution_time_seconds', '?')}s)\n"
            f"   Operator notes: {inc.get('operator_notes', 'None')}"
        )
    return "\n".join(lines)


def _build_historical_summary(incidents: list[dict]) -> dict:
    if not incidents:
        return {"similar_incidents_found": 0}
    times = [
        inc["resolution_time_seconds"]
        for inc in incidents
        if inc.get("resolution_time_seconds")
    ]
    actions_summary = []
    for inc in incidents:
        for a in inc.get("actions_taken", []):
            actions_summary.append(f"{a['parameter']}: {a['to_value']}")
    return {
        "similar_incidents_found": len(incidents),
        "most_recent": incidents[0]["incident_id"],
        "typical_resolution": "; ".join(actions_summary[:3]) if actions_summary else "N/A",
        "avg_resolution_time_seconds": (
            round(sum(times) / len(times)) if times else None
        ),
    }


ACTION_TYPE_KEYWORDS = {
    # Classification runs top-to-bottom and returns on first keyword hit, so
    # more specific action types must come first. Keywords are chosen to be
    # unambiguous — generic terms like "setpoint" are avoided because most
    # SOP steps mention "setpoint" regardless of what's being changed.
    "steam_shutoff":          ["steam", "sv-"],
    "cip_pump_frequency":     ["cip", "frequency", "hz"],
    "agitator_speed_change":  ["agitator"],
    "pump_speed_change":      ["pump", "rpm"],
    "feed_line_switch":       ["feed line", "header", "selector"],
    "valve_position_override": ["valve", "tcv-", "vs-"],
}


def _classify_action_type(parameter: str) -> str:
    param_lower = parameter.lower()
    for action_type, keywords in ACTION_TYPE_KEYWORDS.items():
        if any(kw in param_lower for kw in keywords):
            return action_type
    return "unknown"


def _determine_approval_mode(setpoint_changes: list[dict], area: str, subsystem: str) -> str:
    modes = []
    for change in setpoint_changes:
        action_type = _classify_action_type(change.get("parameter", ""))
        policy = db.automation_policies.find_one({
            "action_type": action_type,
            "area": area,
            "subsystem": subsystem,
        })
        if policy:
            modes.append(policy["approval_mode"])
        else:
            modes.append("human_approval")

    if "advisory_only" in modes:
        return "advisory_only"
    if "human_approval" in modes:
        return "human_approval"
    return "autonomous"


def _call_llm(group: dict, equipment_ctx: str, sop: dict, historical_ctx: str) -> dict | None:
    alarm_list = "\n".join(f"  - {e}" for e in group.get("alarm_events", []))
    telemetry_json = json.dumps(group.get("consolidated_telemetry", {}), indent=2)

    user_prompt = f"""CORRELATED ALARM GROUP:
- Area: {group['area']}
- Subsystem: {group['subsystem']}
- Batch: {group['batch_name']}
- Highest Severity: {group['highest_severity']}
- Alarms in this group:
{alarm_list}
- Consolidated Telemetry:
{telemetry_json}

EQUIPMENT CONTEXT:
{equipment_ctx}

MATCHED STANDARD OPERATING PROCEDURE:
- SOP ID: {sop['sop_id']}
- Title: {sop['title']}
- Content:
{sop['content']}

HISTORICAL INCIDENT CONTEXT:
{historical_ctx}

Based on the correlated alarm group, the matched SOP, equipment context,
and historical incident data, provide your diagnosis and recommended
setpoint changes."""

    print(f"[AGENT 1] Calling LLM ({LLM_MODEL}) for remediation plan...")

    response = llm_client.messages.create(
        model=LLM_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[SUBMIT_ACTION_PLAN_TOOL],
        messages=[{"role": "user", "content": user_prompt}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_action_plan":
            return block.input

    print("[AGENT 1] Warning: LLM did not return a tool_use block.")
    return None


OPEN_ACTION_STATUSES = ("proposed", "approved", "executing")


def _open_action_exists(batch_name: str, root_cause_group: str) -> bool:
    """True if an unresolved action already exists for this batch+root cause.
    Prevents duplicate proposals when the correlator fires repeated groups
    for the same ongoing event. Joins action_queue to correlated_alarm_groups
    via correlation_group_id to match on root_cause_group."""
    if not batch_name or root_cause_group in ("UNKNOWN", ""):
        return False

    open_actions = db.action_queue.find(
        {
            "batch_name": batch_name,
            "status": {"$in": list(OPEN_ACTION_STATUSES)},
        },
        {"correlation_group_id": 1},
    )
    group_ids = [a.get("correlation_group_id") for a in open_actions if a.get("correlation_group_id")]
    if not group_ids:
        return False

    match = db.correlated_alarm_groups.find_one({
        "group_id": {"$in": group_ids},
        "root_cause_group": root_cause_group,
    })
    return match is not None


def evaluate_correlated_group(group_doc: dict):
    group_id = group_doc.get("group_id", "UNKNOWN")
    area = group_doc.get("area", "Mixer3")
    subsystem = group_doc.get("subsystem", "")
    root_cause = group_doc.get("root_cause_group", "UNKNOWN")
    batch_name = group_doc.get("batch_name", "")

    print(
        f"\n[AGENT 1 TRIGGERED] Correlated group: {group_id} | "
        f"{len(group_doc.get('alarm_events', []))} alarm(s) | "
        f"severity={group_doc.get('highest_severity')}"
    )

    # Idempotency: don't propose another action if one is already in flight
    # for this batch + root cause.
    if _open_action_exists(batch_name, root_cause):
        print(
            f"[AGENT 1] Skipping — open action already exists for batch "
            f"{batch_name} / root_cause {root_cause}. Marking group as "
            f"folded into the active remediation."
        )
        db.correlated_alarm_groups.update_one(
            {"group_id": group_id},
            {"$set": {"status": "folded_into_active"}},
        )
        return

    # 1. Equipment context
    equipment_ctx = _get_equipment_context(group_doc.get("tags_involved", []))

    # 2. SOP search
    alarm_text = ". ".join(group_doc.get("alarm_events", []))
    sop = _search_sop(alarm_text, area)
    if not sop:
        print("[AGENT 1] No matching SOP found. Cannot proceed with remediation.")
        return
    print(
        f"[AGENT 1] Matched SOP: {sop['sop_id']} (score: {sop.get('score', 0):.3f})"
    )

    # 3. Historical context
    incidents = _get_historical_context(alarm_text, area, root_cause)
    historical_ctx = _format_historical_context(incidents)
    historical_summary = _build_historical_summary(incidents)
    print(f"[AGENT 1] Found {len(incidents)} historical incident(s).")

    # 4. LLM call
    plan = _call_llm(group_doc, equipment_ctx, sop, historical_ctx)
    if not plan:
        return

    # 5. Automation policy check
    approval_mode = _determine_approval_mode(
        plan.get("setpoint_changes", []), area, subsystem
    )
    status = "approved" if approval_mode == "autonomous" else "proposed"

    # 6. Write to action_queue
    global _action_counter
    _action_counter += 1
    now = datetime.now(timezone.utc)
    action_id = f"ACT-{now.strftime('%Y%m%d-%H%M%S')}-{_action_counter:03d}"

    action_record = {
        "action_id": action_id,
        "created_at": now,
        "updated_at": now,
        "status": status,
        "approval_mode": approval_mode,
        "correlation_group_id": group_id,
        "batch_name": group_doc.get("batch_name", ""),
        "area": area,
        "subsystem": subsystem,
        "source_alarms": group_doc.get("alarm_events", []),
        "sop_applied": plan["sop_id"],
        "diagnosis": plan["diagnosis"],
        "historical_context": historical_summary,
        "setpoint_changes": plan.get("setpoint_changes", []),
        "operational_justification": plan["operational_justification"],
        "severity": plan.get("severity", "HIGH"),
        "approved_by": "SYSTEM" if approval_mode == "autonomous" else None,
        "approved_at": now if approval_mode == "autonomous" else None,
        "rejected_reason": None,
        "execution_result": None,
        "completed_at": None,
    }

    db.action_queue.insert_one(action_record)

    mode_label = {
        "autonomous": "AUTO-APPROVED",
        "human_approval": "AWAITING OPERATOR APPROVAL",
        "advisory_only": "ADVISORY ONLY",
    }

    print(f"\n[AGENT 1 ACTION CREATED] {action_id}")
    print(f"  Status: {status} ({mode_label.get(approval_mode, approval_mode)})")
    print(f"  SOP: {plan['sop_id']}")
    print(f"  Diagnosis: {plan['diagnosis'][:120]}...")
    print(f"  Setpoint changes: {len(plan.get('setpoint_changes', []))}")
    for sc in plan.get("setpoint_changes", []):
        print(
            f"    - {sc['parameter']}: {sc['current_value']} → {sc['target_value']} {sc['unit']} "
            f"({sc.get('sop_reference', '')})"
        )

    # Update correlated group status
    db.correlated_alarm_groups.update_one(
        {"group_id": group_id},
        {"$set": {"status": "remediation_proposed"}},
    )


REACTIVE_SEVERITIES = ("HIGH", "CRITICAL")


def run_reactive_listener():
    print(
        "[AGENT 1] Reactive SOP Matcher listening on 'correlated_alarm_groups' "
        f"via Change Stream (severity filter: {', '.join(REACTIVE_SEVERITIES)})..."
    )
    # WARNING-severity groups come from the Trend agent's predictive alarms —
    # they're informational early-warnings, not something we remediate against.
    # Only react to HIGH / CRITICAL groups, which represent an actual trip.
    pipeline = [{
        "$match": {
            "operationType": "insert",
            "fullDocument.highest_severity": {"$in": list(REACTIVE_SEVERITIES)},
        }
    }]
    try:
        with db.correlated_alarm_groups.watch(pipeline) as stream:
            for change in stream:
                doc = change.get("fullDocument")
                if doc:
                    evaluate_correlated_group(doc)
    except KeyboardInterrupt:
        print("\n[AGENT 1] Reactive SOP Matcher terminated.")


if __name__ == "__main__":
    run_reactive_listener()
