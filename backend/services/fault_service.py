"""Graph-backed fault impact reporting and explicitly hypothetical fault injection."""
from typing import Any, Dict
import networkx as nx
from backend.services.data_service import get_fault_impact, get_asset_graph

FAULT_METRIC_BY_TYPE = {
    "FAN_FAILURE": "fan0_0",
    "POWER_SURGE": "ps0_input_power",
    "THERMAL_SPIKE": "p0_vdd_temp",
    "AMBIENT_HEATWAVE": "ambient",
    "SENSOR_DRIFT": "p1_vdd_temp",
}


def get_cascading_impact_report() -> Dict[str, Any]:
    report = get_fault_impact()
    if report.get("impacts"):
        return report
    return {"available": False, "impacts": [], "message": "No generated fault-impact report is available. Run the ML/data pipeline first."}


def simulate_fault_injection(fault_type: str, severity: float = 1.0) -> Dict[str, Any]:
    """Traverse the generated dependency graph. Results are a scenario, not observations."""
    graph_data = get_asset_graph()
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])
    metric = FAULT_METRIC_BY_TYPE.get(fault_type)
    source_asset = f"M100_NODE_1::{metric}" if metric else None
    node_ids = {str(n.get("asset_id")) for n in nodes}
    if not nodes or not edges:
        return {"available": False, "is_simulated": True, "fault_type": fault_type, "severity": severity,
                "cascade_timeline": [], "message": "Dependency graph output is missing; run the data pipeline first."}
    if source_asset not in node_ids:
        return {"available": False, "is_simulated": True, "fault_type": fault_type, "severity": severity,
                "cascade_timeline": [], "message": f"The generated graph does not contain source asset {source_asset}."}
    graph = nx.DiGraph()
    graph.add_nodes_from(node_ids)
    for edge in edges:
        source = edge.get("source_asset_id")
        target = edge.get("target_asset_id")
        if source in node_ids and target in node_ids:
            graph.add_edge(source, target, relationship=edge.get("relationship_type"))
    reachable = nx.single_source_shortest_path_length(graph, source_asset)
    cascade = []
    for asset_id, depth in sorted(reachable.items(), key=lambda item: (item[1], item[0])):
        cascade.append({
            "stage": int(depth), "asset_id": asset_id,
            "impact_type": "SCENARIO_SOURCE" if depth == 0 else "GRAPH_REACHABLE_DEPENDENCY",
            "severity_score": round(float(severity) / (depth + 1), 4),
            "status": "SCENARIO_SOURCE" if depth == 0 else "POTENTIAL_IMPACT",
            "description": "Hypothetical injected fault source." if depth == 0 else "Reachable through the generated logical dependency graph; physical impact is not validated."
        })
    return {"available": True, "is_simulated": True, "fault_type": fault_type, "severity": severity,
            "primary_origin": source_asset, "affected_components_count": len(cascade),
            "blast_radius_stages": max((item["stage"] for item in cascade), default=0),
            "cascade_timeline": cascade,
            "methodology": "Graph reachability over generated asset relationships; not a learned failure-propagation model."}
