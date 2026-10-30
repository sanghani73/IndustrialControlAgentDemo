from pydantic import BaseModel, Field
from typing import Optional


class SetpointChange(BaseModel):
    parameter: str = Field(description="Actuator tag or setpoint identifier")
    current_value: str
    target_value: str = Field(description="Recommended setpoint per SOP")
    unit: str = Field(description="Engineering units: %, RPM, C, bar, Hz")
    sop_reference: str = Field(description="Which SOP step this comes from")


class AgentActionPlan(BaseModel):
    sop_id: str
    diagnosis: str
    severity: str
    setpoint_changes: list[SetpointChange]
    operational_justification: str


class CorrelatedAlarmGroup(BaseModel):
    group_id: str
    area: str
    subsystem: str
    batch_name: str
    alarm_events: list[str]
    tags_involved: list[str]
    highest_severity: str
    consolidated_telemetry: dict


class ProductionDeviation(BaseModel):
    batch_name: str
    deviation_type: str
    planned_value: str
    actual_value: str
    deviation_minutes: float


class ActionQueueEntry(BaseModel):
    action_id: str
    status: str
    approval_mode: str
    correlation_group_id: str
    batch_name: str
    area: str
    subsystem: str
    sop_applied: str
    diagnosis: str
    setpoint_changes: list[SetpointChange]
    operational_justification: str
    historical_context: Optional[dict] = None
