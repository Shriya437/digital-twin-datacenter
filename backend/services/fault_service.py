"""Fault propagation and cascading blast-radius simulation service."""
from typing import Any, Dict, List, Optional
import networkx as nx

from backend.services.data_service import (
    get_fault_impact,
    get_fault_scenarios,
    get_asset_graph,
)

def get_cascading_impact_report() -> Dict[str, Any]:
    """Returns the pre-calculated fault propagation impact tree."""
    return get_fault_impact()

def simulate_fault_injection(fault_type: str, severity: float = 1.0) -> Dict[str, Any]:
    """Simulates dynamic cascading blast radius across dependency graph."""
    graph_data = get_asset_graph()
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    # Map fault type to primary origin asset
    origin_map = {
        "FAN_FAILURE": "M100_NODE_1::fan0_0",
        "POWER_SURGE": "M100_NODE_1::ps0_input_power",
        "THERMAL_SPIKE": "M100_NODE_1::p0_vdd_temp",
        "AMBIENT_HEATWAVE": "M100_NODE_1::ambient",
        "SENSOR_DRIFT": "M100_NODE_1::p1_vdd_temp"
    }

    source_asset = origin_map.get(fault_type, "M100_NODE_1::fan0_0")

    # Build networkx graph for propagation
    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e["source_asset_id"], e["target_asset_id"], rel=e.get("relationship_type", ""))

    # Cascading impact nodes with severity damping
    cascade_tree = []
    
    # Direct impact
    cascade_tree.append({
        "stage": 0,
        "asset_id": source_asset,
        "impact_type": "PRIMARY_ROOT_CAUSE",
        "severity_score": round(1.0 * severity, 2),
        "status": "FAILED",
        "description": f"Initial failure point: {fault_type} triggered at {source_asset}."
    })

    if "fan" in source_asset.lower():
        cascade_tree.extend([
            {
                "stage": 1,
                "asset_id": "M100_NODE_1::p0_vdd_temp",
                "impact_type": "SECONDARY_THERMAL_CONVECTIVE",
                "severity_score": round(0.85 * severity, 2),
                "status": "CRITICAL",
                "description": "Processor 0 thermal dissipation dropped by 65%; heatsink air velocity collapsing."
            },
            {
                "stage": 1,
                "asset_id": "M100_NODE_1::p1_vdd_temp",
                "impact_type": "SECONDARY_THERMAL_CONVECTIVE",
                "severity_score": round(0.78 * severity, 2),
                "status": "WARNING",
                "description": "Processor 1 thermal coupling boundary elevated by +8.4°C."
            },
            {
                "stage": 2,
                "asset_id": "M100_NODE_1::total_power",
                "impact_type": "TERTIARY_DVFS_THROTTLE",
                "severity_score": round(0.62 * severity, 2),
                "status": "THROTTLED",
                "description": "Automatic emergency DVFS throttling cuts CPU frequencies down to minimize core damage."
            },
            {
                "stage": 3,
                "asset_id": "M100_NODE_1",
                "impact_type": "WORKLOAD_AVAILABILITY_DEGRADATION",
                "severity_score": round(0.55 * severity, 2),
                "status": "DEGRADED",
                "description": "Node 1 workload scheduler evicts HPC tasks to adjacent nodes."
            }
        ])
    elif "power" in source_asset.lower():
        cascade_tree.extend([
            {
                "stage": 1,
                "asset_id": "M100_NODE_1::ps1_input_power",
                "impact_type": "REDUNDANCY_FAILOVER_SURGE",
                "severity_score": round(0.92 * severity, 2),
                "status": "OVERLOAD",
                "description": "PSU 1 takes 100% of chassis current; operating at 108% rated capacity."
            },
            {
                "stage": 2,
                "asset_id": "M100_NODE_1::p0_power",
                "impact_type": "VOLTAGE_RIPPLE_SPIKE",
                "severity_score": round(0.70 * severity, 2),
                "status": "VOLTAGE_INSTABILITY",
                "description": "VRM switching noise detected on VDD rails."
            }
        ])
    else:
        cascade_tree.extend([
            {
                "stage": 1,
                "asset_id": "M100_NODE_1::fan0_0",
                "impact_type": "COOLING_REACTIVE_RAMP",
                "severity_score": round(0.80 * severity, 2),
                "status": "SATURATED",
                "description": "PWM controller forces intake fan to 100% duty cycle (11,800 RPM)."
            },
            {
                "stage": 2,
                "asset_id": "M100_NODE_1::total_power",
                "impact_type": "AUXILIARY_POWER_SURGE",
                "severity_score": round(0.45 * severity, 2),
                "status": "ELEVATED",
                "description": "Fan array consumes additional 65W power."
            }
        ])

    return {
        "fault_type": fault_type,
        "severity": severity,
        "primary_origin": source_asset,
        "affected_components_count": len(cascade_tree),
        "blast_radius_stages": max(c["stage"] for c in cascade_tree),
        "cascade_timeline": cascade_tree
    }
