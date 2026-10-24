from pathlib import Path

from src.data_loader import load_data
from src.asset_registry import build_asset_registry
from src.dependency_graph import (
    build_dependency_graph,
    export_dependency_graph,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs" / "asset_graph"


def main():
    print("Loading telemetry data...")

    df, quality, gap_report, summary = load_data(DATA_DIR)

    print(f"Telemetry rows: {len(df)}")
    print(f"Quality records: {len(quality) if quality is not None else 0}")

    print("\nBuilding asset registry...")
    registry = build_asset_registry(df, quality)

    print("Building dependency graph...")
    graph = build_dependency_graph(registry)

    print("Exporting files...")
    nodes, edges = export_dependency_graph(graph, OUTPUT_DIR)

    print("\nGraph generated successfully!")
    print(f"Nodes: {len(nodes)}")
    print(f"Edges: {len(edges)}")
    print(f"Output folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()