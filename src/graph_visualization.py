"""Create a visual representation of the logical asset/telemetry graph."""
from pathlib import Path
import matplotlib.pyplot as plt
import networkx as nx


def save_graph_plot(graph: nx.DiGraph, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 8))
    pos = nx.spring_layout(graph, seed=42, k=1.1)
    labels = {node: graph.nodes[node].get("display_name", node) for node in graph.nodes}
    nx.draw_networkx(graph, pos, labels=labels, node_size=1900, font_size=7,
                     arrows=True, ax=ax, width=1.2)
    ax.set_title("M100 Node — Logical Telemetry Dependency Graph\nPhysical hardware dependencies are not verified")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
