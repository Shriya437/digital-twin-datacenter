"""FastAPI application for Digital Twin Data Center backend.
Integrates 9 modules: Overview, Digital Twin Rack, Live Telemetry, Plausibility & Staleness,
Anomaly Detection, Root-Cause Diagnosis, Fault Propagation, Predictive Maintenance, and Energy Analytics.
"""
import asyncio
import datetime
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.services.data_service import (
    get_asset_registry,
    get_anomaly_events,
    get_telemetry_df,
    get_metric_reliability,
    get_gap_report,
    get_correlations,
    get_energy_series,
)
from backend.config import ASSET_REGISTRY_CSV, ANOMALY_EVENTS_CSV
from backend.services.twin_service import (
    get_current_twin_state,
    get_state_estimation_comparison,
)
from backend.services.root_cause_service import (
    get_ranked_root_causes,
    get_topology_graph,
)
from backend.services.predictive_service import (
    get_risk_ranked_assets,
    get_forecast_comparison,
)
from backend.services.fault_service import (
    get_cascading_impact_report,
    simulate_fault_injection,
)
from backend.services.energy_service import (
    get_energy_overview,
    run_what_if_simulation,
)
from backend.services.decision_service import (
    validate_and_log_action,
    get_audit_logs,
)

app = FastAPI(
    title="Data Center Digital Twin API",
    description="Full-fidelity Digital Twin platform for high-density compute infrastructure.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class FaultSimulationRequest(BaseModel):
    fault_type: str = Field(default="FAN_FAILURE", description="FAN_FAILURE, POWER_SURGE, THERMAL_SPIKE, AMBIENT_HEATWAVE, SENSOR_DRIFT")
    severity: float = Field(default=1.0, ge=0.1, le=2.0)

class WhatIfRequest(BaseModel):
    reduction_pct: float = Field(default=10.0, ge=0.0, le=50.0)

class DecisionActionRequest(BaseModel):
    action: str
    target_asset: str
    operator: str
    role: str
    risk_score: float = 0.25
    uncertainty_score: float = 0.12
    parameters: Optional[Dict[str, Any]] = None


# -------------------------------------------------------------
# 1. SYSTEM HEALTH & OVERVIEW DASHBOARD
# -------------------------------------------------------------
@app.get("/api/health")
def get_health():
    df = get_telemetry_df()
    return {
        "status": "ONLINE",
        "system_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "datacenter_node": "M100_NODE_1",
        "total_telemetry_records": len(df),
        "api_version": "1.0.0"
    }

@app.get("/api/overview")
def get_overview_dashboard():
    """Module 1: High-level KPIs, asset health distribution, energy usage, and recent incidents."""
    df = get_telemetry_df()
    registry = get_asset_registry()
    anomalies = get_anomaly_events(limit=10)
    energy_info = get_energy_overview()
    ranked_assets = get_risk_ranked_assets()

    # Reliability calculation
    reliability_list = get_metric_reliability()
    scores = [float(r.get("completeness_pct", 100)) for r in reliability_list if r.get("completeness_pct") is not None]
    avg_reliability = round(sum(scores) / len(scores), 2) if scores else None

    # Latest telemetry snapshot
    latest_readings = {}
    if not df.empty:
        last_row = df.iloc[-1].to_dict()
        for k in ["ambient", "p0_vdd_temp", "p1_vdd_temp", "fan0_0", "fan1_0", "total_power"]:
            val = last_row.get(k)
            latest_readings[k] = round(float(val), 2) if val is not None else None

    # Count high-risk assets
    high_risk_count = sum(1 for a in ranked_assets if a.get("risk_level") in ["CRITICAL", "HIGH"])

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "kpis": {
            "monitored_assets_count": len(registry) if ASSET_REGISTRY_CSV.exists() else None,
            "overall_reliability_pct": avg_reliability,
            "active_anomalies_count": len(get_anomaly_events()) if ANOMALY_EVENTS_CSV.exists() else None,
            "total_energy_kwh": energy_info["summary"].get("integrated_total_kWh"),
            "high_risk_equipment_count": high_risk_count,
            "datacenter_pue": energy_info["pue_metrics"].get("pue_value", energy_info["pue_metrics"].get("pue_calculated_value")),
            "chassis_operational_status": "DATA_AVAILABLE" if not df.empty else "DATA_UNAVAILABLE"
        },
        "latest_telemetry": latest_readings,
        "recent_incidents": anomalies[:6],
        "top_risk_assets": ranked_assets[:3]
    }


# -------------------------------------------------------------
# 2. DIGITAL TWIN VISUALIZATION (RACK, CHASSIS, STATE ESTIMATION)
# -------------------------------------------------------------
@app.get("/api/digital-twin/rack")
def get_rack_visualization(tick_index: Optional[int] = Query(None, description="Optional telemetry tick index for replay scrubber")):
    """Module 2: Rack-oriented view of servers and cooling zones, measured vs estimated temps, and sensor staleness."""
    return get_current_twin_state(row_index=tick_index)

@app.get("/api/digital-twin/state-estimation")
def get_state_estimation(limit: int = Query(150, ge=10, le=1000)):
    """Measured vs Estimated temperature time series with residuals and confidence intervals."""
    return get_state_estimation_comparison(limit=limit)


# -------------------------------------------------------------
# 3. ROOT-CAUSE DIAGNOSIS & TOPOLOGY GRAPH
# -------------------------------------------------------------
@app.get("/api/root-cause/hypotheses")
def get_root_cause_hypotheses(limit: int = Query(50, ge=1, le=500)):
    """Module 3: Ranked list of possible root causes with evidence, affected assets, and confidence."""
    return get_ranked_root_causes(limit=limit)

@app.get("/api/root-cause/graph")
def get_dependency_graph():
    """Infrastructure dependency graph nodes and edges."""
    return get_topology_graph()

@app.get("/api/root-cause/correlations")
def get_sensor_correlations():
    """Spearman correlation matrix and automated physical domain interpretations."""
    return get_correlations()


# -------------------------------------------------------------
# 4. PREDICTIVE MAINTENANCE & HORIZON FORECASTING
# -------------------------------------------------------------
@app.get("/api/predictive-maintenance/assets")
def get_predictive_maintenance_assets():
    """Module 4: Risk-ranked asset list with early warnings, downstream impacts, and maintenance tasks."""
    return get_risk_ranked_assets()

@app.get("/api/predictive-maintenance/forecasts")
def get_predictive_forecasts():
    """1-min, 5-min, 15-min temperature predictions and model evaluation metrics."""
    return get_forecast_comparison()


# -------------------------------------------------------------
# 5. FAULT PROPAGATION & BLAST RADIUS
# -------------------------------------------------------------
@app.get("/api/fault-propagation/impact")
def get_fault_impact():
    """Logical fault propagation reachability and cascading depth tree."""
    return get_cascading_impact_report()

@app.post("/api/fault-propagation/simulate")
def simulate_fault(req: FaultSimulationRequest):
    """Interactive blast radius simulation upon injected fault."""
    return simulate_fault_injection(fault_type=req.fault_type, severity=req.severity)


# -------------------------------------------------------------
# 6. ENERGY ANALYTICS & WHAT-IF SIMULATOR
# -------------------------------------------------------------
@app.get("/api/energy/overview")
def get_energy_metrics():
    """Energy analytics, integrated kWh, and PUE compliance status."""
    return get_energy_overview()

@app.get("/api/energy/timeseries")
def get_energy_timeseries(limit: int = Query(200, ge=10, le=1000)):
    """Interval energy integration data."""
    return get_energy_series(limit=limit)

@app.post("/api/energy/what-if")
def simulate_what_if_energy(req: WhatIfRequest):
    """What-if simulation calculating power and energy reductions, temp drop, and CO2 savings."""
    return run_what_if_simulation(reduction_pct=req.reduction_pct)


# -------------------------------------------------------------
# 7. TELEMETRY, RELIABILITY & ANOMALIES
# -------------------------------------------------------------
@app.get("/api/telemetry/history")
def get_telemetry_history(
    offset: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    metric: Optional[str] = Query(None)
):
    df = get_telemetry_df()
    if df.empty:
        return {"total": 0, "records": []}

    total = len(df)
    subset = df.iloc[offset : offset + limit].copy()
    if metric and metric in subset.columns:
        subset = subset[["timestamp", metric]]

    from backend.services.data_service import sanitize_records
    records = sanitize_records(subset)
    # Ensure ISO string timestamps
    for r in records:
        if "timestamp" in r and hasattr(r["timestamp"], "isoformat"):
            r["timestamp"] = r["timestamp"].isoformat()
        else:
            r["timestamp"] = str(r.get("timestamp", ""))

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "records": records
    }

@app.get("/api/telemetry/reliability")
def get_reliability_report():
    return {
        "metrics": get_metric_reliability(),
        "timestamp_gaps": get_gap_report(limit=100)
    }

@app.get("/api/telemetry/anomalies")
def get_anomalies(limit: int = Query(100, ge=1, le=1000)):
    return get_anomaly_events(limit=limit)


# -------------------------------------------------------------
# 8. DECISION SUPPORT & AUDIT LOGS
# -------------------------------------------------------------
@app.post("/api/decision-support/validate")
def execute_decision_validation(req: DecisionActionRequest):
    """Validates action against safety gate criteria, checks role authorization, and logs to audit trail."""
    result = validate_and_log_action(
        action=req.action,
        target_asset=req.target_asset,
        operator=req.operator,
        role=req.role,
        risk_score=req.risk_score,
        uncertainty_score=req.uncertainty_score,
        parameters=req.parameters
    )
    return result

@app.get("/api/decision-support/audit-logs")
def get_audit_trail(limit: int = Query(50, ge=1, le=200)):
    return get_audit_logs(limit=limit)


# -------------------------------------------------------------
# 9. REAL-TIME TELEMETRY WEBSOCKET STREAM
# -------------------------------------------------------------
@app.websocket("/ws/telemetry")
async def websocket_telemetry_stream(websocket: WebSocket):
    """Streams live / replayed telemetry records with delay jitter and state estimation."""
    await websocket.accept()
    df = get_telemetry_df()
    if df.empty:
        await websocket.send_json({"error": "No telemetry dataset available"})
        await websocket.close()
        return

    total_rows = len(df)
    current_index = 0
    playback_speed = 1.0  # seconds between ticks

    try:
        while True:
            # Check for client control messages
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                data = json.loads(msg)
                if "speed" in data:
                    playback_speed = max(0.05, float(data["speed"]))
                if "seek" in data:
                    current_index = max(0, min(total_rows - 1, int(data["seek"])))
            except asyncio.TimeoutError:
                pass
            except Exception:
                pass

            # Prepare telemetry packet
            state = get_current_twin_state(row_index=current_index)
            packet = {
                "type": "TELEMETRY_FRAME",
                "frame_id": current_index + 1,
                "total_frames": total_rows,
                "data": state
            }

            await websocket.send_json(packet)

            current_index = (current_index + 1) % total_rows
            await asyncio.sleep(playback_speed)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
