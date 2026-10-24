"""Graph reachability queries with explicit warnings about unverified topology."""
import pandas as pd
import networkx as nx


def assess_potential_impact(graph: nx.DiGraph, asset_id: str) -> pd.DataFrame:
    if asset_id not in graph:
        raise ValueError(f"Unknown asset ID: {asset_id}")
    rows = []
    for direction, nodes in (("downstream", nx.descendants(graph, asset_id)),
                             ("upstream", nx.ancestors(graph, asset_id))):
        for related in sorted(nodes):
            path = (nx.shortest_path(graph, asset_id, related) if direction == "downstream"
                    else nx.shortest_path(graph, related, asset_id))
            edges = list(zip(path[:-1], path[1:]))
            simulated_or_unverified = any(
                graph.edges[u, v].get("physical_dependency_verified") is not True for u, v in edges
            )
            rows.append({
                "source_asset_id": asset_id,
                "related_asset_id": related,
                "direction": direction,
                "path": " -> ".join(path),
                "path_contains_unverified_physical_dependency": simulated_or_unverified,
                "impact_status": "graph_reachability_only_not_physical_impact_prediction",
            })
    return pd.DataFrame(rows, columns=["source_asset_id", "related_asset_id", "direction", "path",
                                      "path_contains_unverified_physical_dependency", "impact_status"])
