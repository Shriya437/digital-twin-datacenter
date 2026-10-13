"""Build, validate, query, and export a logical telemetry dependency graph."""
from pathlib import Path
import json
import pandas as pd
import networkx as nx


def build_dependency_graph(registry: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for _, row in registry.iterrows():
        attrs = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
        graph.add_node(str(row["asset_id"]), **attrs)
    for _, row in registry.iterrows():
        parent = row.get("parent_asset_id")
        if isinstance(parent, str) and parent:
            graph.add_edge(parent, str(row["asset_id"]),
                            relationship_type="has_telemetry_metric",
                            evidence="metric column associated with monitored node",
                            evidence_status="dataset_backed_logical_association",
                            is_simulated=False, physical_dependency_verified=False)
    validate_graph(graph)
    return graph


def validate_graph(graph: nx.DiGraph) -> None:
    if not graph.is_directed():
        raise ValueError("Dependency graph must be directed")
    if graph.number_of_nodes() == 0:
        raise ValueError("Dependency graph cannot be empty")
    for node in graph.nodes:
        if not isinstance(node, str) or not node.strip():
            raise ValueError("Every graph node must have a non-empty string ID")
    for u, v in graph.edges:
        if u not in graph or v not in graph:
            raise ValueError(f"Relationship references unknown node: {u} -> {v}")


def export_dependency_graph(graph: nx.DiGraph, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    nodes = [{"asset_id": node, **attrs} for node, attrs in graph.nodes(data=True)]
    edges = [{"source_asset_id": u, "target_asset_id": v, **attrs}
             for u, v, attrs in graph.edges(data=True)]
    pd.DataFrame(nodes).to_csv(output_dir / "asset_registry.csv", index=False)
    pd.DataFrame(edges).to_csv(output_dir / "asset_relationships.csv", index=False)
    with open(output_dir / "asset_graph.json", "w", encoding="utf-8") as f:
        json.dump({"directed": True,
                   "graph_note": "Logical telemetry associations only; physical cooling/power topology is not verified.",
                   "nodes": nodes, "edges": edges}, f, indent=2, default=str)
    return nodes, edges


def related_assets(graph: nx.DiGraph, asset_id: str):
    if asset_id not in graph:
        raise ValueError(f"Unknown asset ID: {asset_id}")
    return {"upstream": sorted(nx.ancestors(graph, asset_id)),
            "downstream": sorted(nx.descendants(graph, asset_id)),
            "direct_upstream": sorted(graph.predecessors(asset_id)),
            "direct_downstream": sorted(graph.successors(asset_id))}
