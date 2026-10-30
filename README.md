# Autonomous Industrial Control Agent

**MongoDB Atlas + LLM for Real-Time Plant Fault Detection, Diagnosis, and Remediation**

An autonomous AI agent system for a chemical batch mixing plant that monitors real-time telemetry, correlates alarms into root causes, retrieves Standard Operating Procedures via semantic search, enriches decisions with historical operator context, and proposes structured remediation actions — all with human-in-the-loop approval.

Built on **MongoDB Atlas** (Time Series Collections, Change Streams, Vector Search with Automated Embeddings powered by Voyage AI, Aggregation Pipelines) and an **LLM** reasoning engine (configurable via `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`, with support for a Grove-style API gateway or a direct provider endpoint; structured output via tool_use).

---

## Architecture

```
                  ┌─────────────────────────────────────────────────────────────┐
                  │                    Plant Simulators                         │
                  │        (Telemetry Streams + Discrete Alarm Events)          │
                  └──────────┬──────────────────────────────┬──────────────────┘
                             │                              │
                             v                              v
          ┌──────────────────────────────┐   ┌──────────────────────────────┐
          │      sensor_telemetry        │   │        plant_alarms          │
          │    (Time Series Collection)  │   │    (Standard Collection)     │
          └──────────────┬───────────────┘   └──────────────┬───────────────┘
                         │                                  │
                         │ Periodic                         │ Change Stream
                         │ Aggregation                      │
                         v                                  v
          ┌──────────────────────────────┐   ┌──────────────────────────────┐
          │          Agent 2             │   │          Agent 3             │
          │    (Trend Analysis)          │   │    (Alarm Correlator)        │
          │  Sliding window detection    │   │  5s debounce + root cause   │
          └──────────────┬───────────────┘   │  grouping via alarm_defs    │
                         │                   └──────────────┬───────────────┘
                         │ Emits warning                    │
                         │ to plant_alarms                  │ Writes correlated group
                         └──────────┐                       v
                                    │        ┌──────────────────────────────┐
                                    │        │  correlated_alarm_groups     │
                                    │        └──────────────┬───────────────┘
                                    │                       │ Change Stream
                                    │                       v
                                    │        ┌──────────────────────────────┐
                                    └───────>│          Agent 1             │
                                             │  (Reactive SOP Matcher)      │
                                             │                              │
                                             │  1. equipment_registry       │
                                             │     (context enrichment)     │
                                             │  2. plant_sops               │
                                             │     ($vectorSearch/autoEmbed)│
                                             │  3. incident_history         │
                                             │     ($vectorSearch + query)  │
                                             │  4. LLM (tool_use)          │
                                             │  5. automation_policies      │
                                             │     (approval mode check)   │
                                             └──────────────┬───────────────┘
                                                            │
                                                            v
                                             ┌──────────────────────────────┐
                                             │        action_queue          │
                                             │  proposed -> approved ->     │
                                             │  executing -> completed      │
                                             └──────────────┬───────────────┘
                                                            │
                                                            v
                                             ┌──────────────────────────────┐
                                             │      Flask Dashboard         │
                                             │  (Approve / Reject actions)  │
                                             └──────────────────────────────┘

          ┌──────────────────────────────┐
          │          Agent 4             │   Periodic polling
          │   (Production Monitor)       │──────────────────────>
          │   Plan vs Actual deviation   │   production_plans
          └──────────────────────────────┘   production_actuals
```

---

## Use Cases and Scenarios

This demo simulates three real-world failure scenarios based on actual Siemens WinCC Runtime telemetry from batch operations on **Mixer3** (a chemical batch mixing vessel).

### SCN-01: Dosing Starvation and Negative Flow Gradient

| | |
|---|---|
| **Subsystem** | M3MX3 / CHARGEFL (water and solvent dosing phase) |
| **What happens** | Water flow rate drops from 2.8 to 0.45 kg/s while the dosing control valve is already at 95% open. Supply pressure degrades from 2.3 to 1.38 bar. |
| **Root cause** | Upstream supply header cavitation or pump degradation |
| **Alarms fired** | "Water Dosing too slow", "Limit value (high) for the negative gradient" |
| **Tags involved** | 37-VS-4520 (valve), 37-FT-4502 (flow), 37-PT-4501 (pressure) |
| **SOP matched** | SOP-MIX3-4520-DOSE |
| **Remediation** | Override valve +12%, increase pump speed to 1750 RPM, switch to Header-B if pressure stays low |

### SCN-02: Thermal Excursion and Valve Actuator Lag

| | |
|---|---|
| **Subsystem** | M3MX3 / HEATCOOL (heating and cooling phase) |
| **What happens** | Process temperature spikes from 65 C past the 82 C alarm limit. The jacket cooling valve readback drops to 15% despite a 60% setpoint, indicating an actuator fault. |
| **Root cause** | Exothermic runaway combined with cooling valve positioner failure |
| **Alarms fired** | "37-TT-4521 PV - High alarm limit violated", "37-TCV-4521 Rbk - Low warning limit violated" |
| **Tags involved** | 37-TT-4521 (temperature), 37-TCV-4521 (cooling valve), 37-SV-4510 (steam) |
| **SOP matched** | SOP-MIX3-4521-THERM |
| **Remediation** | Set cooling valve to 85%, increase agitator speed +20 RPM, shut off steam valve to 0% |

### SCN-03: CIP Loop Cavitation and Starvation

| | |
|---|---|
| **Subsystem** | M3CIP8 (Clean-in-Place loop 8) |
| **What happens** | CIP supply flow drops from 8.5 to 1.2 m3/h. Return pressure falls from 2.1 to 0.3 bar. Audible cavitation. |
| **Root cause** | Air entrainment from low CIP supply tank level, clogged suction strainer |
| **Alarms fired** | "30-FIC-9031 PV - Low alarm limit violated", "30-PT-9041 PV - Low warning limit violated" |
| **Tags involved** | 30-FIC-9031 (flow controller), 30-PT-9041 (pressure) |
| **SOP matched** | SOP-MIX3-9031-CIP |
| **Remediation** | Increase pump drive frequency +8 Hz, open return valve from 30% to 55% |

---

## Key MongoDB Features Demonstrated

| Feature | How It Is Used |
|---|---|
| **Time Series Collections** | `sensor_telemetry` stores high-frequency process measurements (5-second intervals) with `timeField`, `metaField`, and `granularity` optimized for temporal queries |
| **Change Streams** | Agent 3 watches `plant_alarms` for new inserts in real-time. Agent 1 watches `correlated_alarm_groups`. No polling, no external message broker. |
| **Vector Search with Automated Embeddings** | Three `autoEmbed` indexes (Voyage AI `voyage-4-large`) on `plant_sops`, `alarm_definitions`, and `incident_history`. Zero client-side embedding code — Atlas vectorizes on write and on query. |
| **Aggregation Pipelines** | Trend detection (sliding window over time series), alarm correlation (time-windowed grouping), production plan-vs-actual comparison (`$lookup` across collections) |
| **Flexible Document Model** | 11 collections with different shapes: equipment hierarchies with dependency chains, alarm definitions with root cause groups, SOPs with linked codes, incident narratives, production plans with nested batch schedules, action queue with state machine lifecycle |

---

## Key AI Features

| Feature | Description |
|---|---|
| **Alarm Correlation** | Groups related alarms into a single root-cause group using a 5-second debounce, `alarm_definitions` root cause mappings, and equipment dependency chain traversal. Prevents alarm flooding. |
| **Semantic SOP Retrieval** | `$vectorSearch` with `autoEmbed` finds the most relevant Standard Operating Procedure based on the natural-language description of the alarm condition. |
| **Historical Context Retrieval** | Dual retrieval strategy: (1) vector search on `incident_history` narratives for semantically similar past events, (2) structured query by root cause group for exact matches. Deduplicates and provides the top 3 to the LLM. |
| **LLM-Grounded Remediation** | The LLM generates a structured action plan (diagnosis, setpoint changes with SOP step references, justification) strictly grounded in the matched SOP. Uses `tool_use` for reliable structured output. |
| **Human-in-the-Loop Approval** | Actions flow through a state machine: `proposed` -> `approved` -> `executing` -> `completed`. Automation policies determine per-action-type autonomy (autonomous, human_approval, or advisory_only). |
| **Production Plan Monitoring** | Agent 4 periodically compares production plan schedules against actual batch execution state, detecting late starts, schedule deviations, and alarm-related holds. |

---

## Prerequisites

- **Python** 3.10 or later
- **MongoDB Atlas** cluster (M10 or higher for Change Streams support)
- **Atlas Vector Search** enabled on the cluster (indexes are created automatically by the seed script)
- **LLM API credentials** (direct provider API key or Grove-style API gateway key)

---

## Quick Start

### 1. Clone and configure

```bash
cd IndustrialControlAgentDemo
cp .env.example .env
```

Edit `.env` with your credentials:

```
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/?retryWrites=true&w=majority
LLM_API_KEY=<your-llm-api-key>
LLM_BASE_URL=<your-llm-gateway-url>       # omit this line for a direct provider endpoint
LLM_MODEL=<your-model-id>                 # e.g. the model ID exposed by your gateway
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Seed the database

```bash
python -m seed.seed_all
```

This automatically:
- Creates the time series collection (`sensor_telemetry`)
- Populates all reference data (equipment registry, alarm definitions, SOPs, historical incidents, production plans, automation policies)
- Creates standard indexes on all collections
- Creates three Atlas Vector Search indexes with Automated Embeddings (Voyage AI):
  - `sop_auto_vector_index` on `plant_sops`
  - `alarm_def_auto_vector_index` on `alarm_definitions`
  - `incident_auto_vector_index` on `incident_history`
- Waits for vector search indexes to become active (up to 2 minutes)

### 4. Run the demo

**Option A — All-in-one orchestrator:**

```bash
python run_demo.py
```

**Option B — Individual terminals (recommended for demos):**

```bash
# Terminal 1: Dashboard
python -m dashboard.app

# Terminal 2: Alarm Correlator (Agent 3)
python -m agents.agent_correlator

# Terminal 3: Reactive SOP Matcher (Agent 1)
python -m agents.agent_reactive

# Terminal 4: Production Monitor (Agent 4)
python -m agents.agent_production
```

### 5. Trigger a scenario

In a separate terminal:

```bash
python -m simulate.simulate_scenario --scenario scn-01
```

Then open `http://localhost:5001` to see the results on the dashboard.

---

## Project Structure

```
IndustrialControlAgentDemo/
├── .env.example                     # Environment variable template
├── requirements.txt                 # Python dependencies
├── config.py                        # MongoDB + LLM client setup
├── models.py                        # Pydantic domain models
├── run_demo.py                      # All-in-one orchestrator
│
├── seed/                            # Database seeding scripts
│   ├── seed_all.py                  # Master seeder (runs all sub-seeders)
│   ├── seed_equipment.py            # Equipment registry (14 records)
│   ├── seed_alarm_definitions.py    # Alarm code catalog (7 records)
│   ├── seed_sops.py                 # Standard Operating Procedures (3 records)
│   ├── seed_incidents.py            # Historical incidents (6 records)
│   └── seed_production_plan.py      # Production plan + automation policies
│
├── simulate/                        # Telemetry and alarm simulators
│   ├── simulate_telemetry.py        # Sensor data generators + alarm emitters
│   └── simulate_scenario.py         # CLI scenario runner (scn-01/02/03/all)
│
├── agents/                          # AI agent modules
│   ├── agent_correlator.py          # Agent 3: Alarm correlation
│   ├── agent_reactive.py            # Agent 1: SOP match + LLM remediation
│   ├── agent_trend.py               # Agent 2: Trend detection
│   └── agent_production.py          # Agent 4: Production plan monitoring
│
└── dashboard/                       # Flask web dashboard
    ├── app.py                       # Flask app factory
    ├── routes.py                    # API + page routes
    ├── static/css/style.css
    ├── static/js/dashboard.js
    └── templates/
        ├── base.html                # Layout with navigation
        ├── overview.html            # Summary dashboard
        ├── actions.html             # Action queue with approve/reject
        ├── production.html          # Plan vs actual view
        └── alarms.html              # Correlated alarm groups
```

---

## Collections Reference

| Collection | Type | Records | Purpose |
|---|---|---|---|
| `sensor_telemetry` | Time Series | Dynamic | High-frequency process measurements (5s intervals) |
| `plant_alarms` | Standard | Dynamic | Discrete alarm and warning events |
| `correlated_alarm_groups` | Standard | Dynamic | Grouped alarms identified as sharing a root cause |
| `plant_sops` | Standard + autoEmbed | 3 | Standard Operating Procedures (vectorized by Atlas) |
| `equipment_registry` | Standard | 14 | Equipment hierarchy with tags, ranges, dependencies |
| `alarm_definitions` | Standard + autoEmbed | 7 | Alarm code catalog with root cause mappings |
| `incident_history` | Standard + autoEmbed | 6 | Historical incidents with operator actions and outcomes |
| `action_queue` | Standard | Dynamic | Remediation actions with approval state machine |
| `automation_policies` | Standard | 6 | Per-action-type autonomy levels |
| `production_plans` | Standard | 1 | Shift production schedule with batch sequences |
| `production_actuals` | Standard | Dynamic | Actual batch execution state |

---

## Configuration

| Variable | Required | Description |
|---|---|---|
| `MONGODB_URI` | Yes | MongoDB Atlas connection string |
| `LLM_API_KEY` | Yes | API key for the LLM provider (direct or via a Grove-style gateway) |
| `LLM_BASE_URL` | No | LLM gateway URL. Omit for a direct provider endpoint. |
| `LLM_MODEL` | No | Model ID exposed by your gateway or provider. |
