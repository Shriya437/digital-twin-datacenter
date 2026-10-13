"""Trace downstream logical impact and run Module 5 analytics."""

from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from sklearn.metrics import precision_score, recall_score, f1_score


# --------------------------------------------------
# 1. PATHS AND CONFIGURATION
# --------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[1]

GRAPH_DIR = ROOT_DIR / "outputs"
OUTPUT_DIR = ROOT_DIR / "outputs" / "fault_propagation"
DATA_DIR = ROOT_DIR / "data"

GRAPH_FILE = GRAPH_DIR / "asset_graph.json"
REGISTRY_FILE = GRAPH_DIR / "asset_registry.csv"
RELATIONSHIPS_FILE = GRAPH_DIR / "asset_relationships.csv"

TELEMETRY_FILE = DATA_DIR / "m100_node1_digital_twin.csv"
GROUND_TRUTH_FILE = DATA_DIR / "fault_scenario_ground_truth.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 2. LOAD ASSET GRAPH
# --------------------------------------------------

def load_asset_graph():
    """Load graph, registry, and relationship files."""

    for path in [GRAPH_FILE, REGISTRY_FILE, RELATIONSHIPS_FILE]:
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")

    with open(GRAPH_FILE, "r", encoding="utf-8") as file:
        graph_data = json.load(file)

    registry = pd.read_csv(REGISTRY_FILE)
    relationships = pd.read_csv(RELATIONSHIPS_FILE)

    if "asset_id" not in registry.columns:
        raise ValueError("asset_registry.csv must contain asset_id.")

    graph = nx.DiGraph()

    # Add asset nodes and their metadata.
    for node in graph_data["nodes"]:
        asset_id = str(node["asset_id"])

        attributes = {
            key: value
            for key, value in node.items()
            if key != "asset_id"
        }

        graph.add_node(asset_id, **attributes)

    # Add directed relationships.
    for edge in graph_data["edges"]:
        source = str(edge["source_asset_id"])
        target = str(edge["target_asset_id"])

        if source in graph and target in graph:
            attributes = {
                key: value
                for key, value in edge.items()
                if key not in {"source_asset_id", "target_asset_id"}
            }

            graph.add_edge(source, target, **attributes)

    registry["asset_id"] = registry["asset_id"].astype(str)

    return graph, registry, relationships


# --------------------------------------------------
# 3. ORIGINAL FAULT-IMPACT TRACING
# --------------------------------------------------

def trace_fault(graph, registry, fault_asset_id):
    """Find assets reachable downstream from a fault source."""

    fault_asset_id = str(fault_asset_id)

    if fault_asset_id not in graph:
        raise ValueError(
            f"Asset '{fault_asset_id}' was not found in the graph."
        )

    registry_by_id = registry.set_index("asset_id").to_dict("index")

    affected_assets = []
    descendants = nx.descendants(graph, fault_asset_id)

    # Include the source asset itself.
    impacted = {fault_asset_id: 0}

    for asset_id in descendants:
        impacted[asset_id] = nx.shortest_path_length(
            graph,
            source=fault_asset_id,
            target=asset_id
        )

    for asset_id, depth in sorted(
        impacted.items(),
        key=lambda item: (item[1], item[0])
    ):
        metadata = registry_by_id.get(asset_id, {})
        path = nx.shortest_path(graph, fault_asset_id, asset_id)

        affected_assets.append({
            "fault_source": fault_asset_id,
            "asset_id": asset_id,
            "display_name": metadata.get("display_name", asset_id),
            "asset_type": metadata.get("asset_type", "unknown"),
            "impact_depth": depth,
            "impact_category": (
                "fault_source" if depth == 0
                else "directly_reachable" if depth == 1
                else "indirectly_reachable"
            ),
            "relationship_path": " -> ".join(path),
            "physical_impact_verified": False,
        })

    return pd.DataFrame(affected_assets)


# --------------------------------------------------
# 4. CONTROLLED FAULT-PROPAGATION SCENARIOS
# --------------------------------------------------

def run_propagation_scenario(
    graph,
    source_asset_id,
    scenario_id,
    scenario_type,
    injected_effects
):
    """Simulate logical reachability from an injected fault source."""

    source_asset_id = str(source_asset_id)

    if source_asset_id not in graph:
        raise ValueError(f"Unknown source asset: {source_asset_id}")

    descendants = nx.descendants(graph, source_asset_id)
    impacted = {source_asset_id: 0}

    for asset_id in descendants:
        impacted[asset_id] = nx.shortest_path_length(
            graph,
            source=source_asset_id,
            target=asset_id
        )

    rows = []

    for asset_id, depth in sorted(
        impacted.items(),
        key=lambda item: (item[1], item[0])
    ):
        rows.append({
            "scenario_id": scenario_id,
            "scenario_type": scenario_type,
            "source_asset_id": source_asset_id,
            "affected_asset_id": asset_id,
            "impact_depth": depth,
            "impact_basis": (
                "injected_source"
                if depth == 0
                else "graph_reachability_only"
            ),
            "injected_effects": json.dumps(injected_effects),
            "is_simulated": True,
            "physical_impact_verified": False
        })

    return pd.DataFrame(rows)


# --------------------------------------------------
# 5. OPTIONAL PROPAGATION EVALUATION
# --------------------------------------------------

def evaluate_propagation(scenario_result):
    """Evaluate propagation only when ground-truth labels exist."""

    if not GROUND_TRUTH_FILE.exists():
        print(
            "\nGround truth not found. Skipping propagation evaluation."
        )
        print(
            "Create and validate data/fault_scenario_ground_truth.csv "
            "before reporting precision, recall, or F1."
        )
        return

    truth = pd.read_csv(GROUND_TRUTH_FILE)

    required = {
        "scenario_id",
        "affected_asset_id",
        "expected_affected"
    }

    if not required.issubset(truth.columns):
        raise ValueError(
            f"Ground truth must contain: {sorted(required)}"
        )

    truth["scenario_id"] = truth["scenario_id"].astype(str)
    truth["affected_asset_id"] = truth["affected_asset_id"].astype(str)

    if not truth["expected_affected"].isin([0, 1]).all():
        raise ValueError("expected_affected must contain only 0 or 1.")

    if truth.duplicated(
        subset=["scenario_id", "affected_asset_id"]
    ).any():
        raise ValueError(
            "Ground truth must have one row per scenario and asset."
        )

    predictions = scenario_result[
        ["scenario_id", "affected_asset_id"]
    ].drop_duplicates().copy()

    predictions["scenario_id"] = predictions["scenario_id"].astype(str)
    predictions["affected_asset_id"] = (
        predictions["affected_asset_id"].astype(str)
    )
    predictions["predicted_affected"] = 1

    evaluation = truth.merge(
        predictions,
        on=["scenario_id", "affected_asset_id"],
        how="left"
    )

    evaluation["predicted_affected"] = (
        evaluation["predicted_affected"].fillna(0).astype(int)
    )

    y_true = evaluation["expected_affected"].astype(int)
    y_pred = evaluation["predicted_affected"]

    metrics = {
        "precision": precision_score(
            y_true, y_pred, zero_division=0
        ),
        "recall": recall_score(
            y_true, y_pred, zero_division=0
        ),
        "f1_score": f1_score(
            y_true, y_pred, zero_division=0
        )
    }

    evaluation.to_csv(
        OUTPUT_DIR / "propagation_evaluation_details.csv",
        index=False
    )

    pd.DataFrame([metrics]).to_csv(
        OUTPUT_DIR / "propagation_evaluation.csv",
        index=False
    )

    print("\nPropagation evaluation:")
    print(metrics)


# --------------------------------------------------
# 6. ENERGY AND COOLING ANALYTICS
# --------------------------------------------------

def run_energy_cooling_analytics():
    """Estimate energy use and analyze power-temperature relationships."""

    if not TELEMETRY_FILE.exists():
        print(f"\nTelemetry file not found: {TELEMETRY_FILE}")
        print("Skipping energy and cooling analytics.")
        return

    df = pd.read_csv(TELEMETRY_FILE)

    if "timestamp" not in df.columns:
        print("Telemetry has no timestamp column. Skipping analytics.")
        return

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], utc=True, errors="coerce"
    )

    df = (
        df.dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"])
        .reset_index(drop=True)
    )

    if df.empty:
        print("No valid telemetry timestamps. Skipping analytics.")
        return

    # Convert available telemetry measurements to numeric values.
    numeric_candidates = [
        "total_power",
        "p0_vdd_temp",
        "p1_vdd_temp",
        "ambient",
        "p0_power",
        "p1_power",
        "fan0_0",
        "fan1_0"
    ]

    for col in numeric_candidates:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.replace([np.inf, -np.inf], np.nan, inplace=True)

    # Reuse the existing segment_id when available.
    if "segment_id" not in df.columns:
        gap_seconds = df["timestamp"].diff().dt.total_seconds()
        typical_interval = gap_seconds[gap_seconds > 0].median()

        if pd.isna(typical_interval):
            df["segment_id"] = 0
        else:
            new_segment = gap_seconds > 1.5 * typical_interval
            new_segment.iloc[0] = True
            df["segment_id"] = new_segment.cumsum()

    # ---------------- ENERGY ESTIMATION ----------------

    power_col = "total_power"

    if power_col not in df.columns:
        print("\ntotal_power is unavailable; energy analysis skipped.")
    else:
        energy_df = df[
            ["timestamp", "segment_id", power_col]
        ].copy()

        energy_df = (
            energy_df.dropna(subset=["timestamp", power_col])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )

        energy_df["interval_seconds"] = (
            energy_df["timestamp"].diff().dt.total_seconds()
        )

        positive_intervals = energy_df.loc[
            energy_df["interval_seconds"] > 0,
            "interval_seconds"
        ]

        typical_interval = positive_intervals.median()

        if pd.isna(typical_interval):
            print("Insufficient timestamps for energy analysis.")
        else:
            valid_interval = (
                (energy_df["interval_seconds"] > 0)
                & (
                    energy_df["interval_seconds"]
                    <= 1.5 * typical_interval
                )
                & (
                    energy_df["segment_id"]
                    == energy_df["segment_id"].shift(1)
                )
            )

            previous_power = energy_df[power_col].shift(1)

            # Trapezoidal integration.
            # Assumes total_power is measured in watts.
            energy_df["energy_Wh"] = np.where(
                valid_interval,
                (
                    (previous_power + energy_df[power_col]) / 2
                ) * energy_df["interval_seconds"] / 3600,
                0.0
            )

            total_energy_wh = energy_df["energy_Wh"].sum()

            energy_df.to_csv(
                OUTPUT_DIR / "energy_analysis.csv",
                index=False
            )

            print("\nEstimated energy over valid intervals:")
            print(f"{total_energy_wh:.4f} Wh")
            print(f"{total_energy_wh / 1000:.6f} kWh")

    # ---------------- POWER-TEMPERATURE ANALYSIS ----------------

    comparison_cols = [
        col for col in [
            "total_power",
            "p0_vdd_temp",
            "p1_vdd_temp",
            "ambient"
        ]
        if col in df.columns
    ]

    if len(comparison_cols) >= 2:
        correlation = df[comparison_cols].corr(numeric_only=True)

        correlation.to_csv(
            OUTPUT_DIR / "power_temperature_correlation.csv"
        )

        print("\nPower and temperature correlations:")
        print(correlation)

    if (
        "total_power" in df.columns
        and "p0_vdd_temp" in df.columns
    ):
        plot_df = df[
            ["total_power", "p0_vdd_temp"]
        ].dropna()

        if not plot_df.empty:
            plt.figure(figsize=(8, 5))
            plt.scatter(
                plot_df["total_power"],
                plot_df["p0_vdd_temp"],
                alpha=0.5
            )

            plt.xlabel("Total power (source units)")
            plt.ylabel("Processor temperature (source units)")
            plt.title("Power and Temperature Relationship")
            plt.tight_layout()

            plt.savefig(
                OUTPUT_DIR / "power_temperature_relationship.png",
                dpi=180
            )
            plt.close()

    print("\nEnergy and cooling analytics completed.")


# --------------------------------------------------
# 7. WHAT-IF POWER COMPARISON
# --------------------------------------------------

def run_what_if_analysis():
    """Compare baseline power with hypothetical reductions."""

    if not TELEMETRY_FILE.exists():
        print("\nTelemetry file unavailable; skipping what-if analysis.")
        return

    df = pd.read_csv(TELEMETRY_FILE)

    if "total_power" not in df.columns:
        print("total_power is unavailable; what-if analysis skipped.")
        return

    baseline_power = pd.to_numeric(
        df["total_power"], errors="coerce"
    ).replace([np.inf, -np.inf], np.nan).dropna()

    if baseline_power.empty:
        print("No valid total_power readings for what-if analysis.")
        return

    baseline_mean = baseline_power.mean()
    scenarios = []

    for reduction in [0.00, 0.05, 0.10, 0.15]:
        hypothetical_power = baseline_mean * (1 - reduction)

        scenarios.append({
            "scenario": f"{reduction:.0%}_power_reduction",
            "assumed_reduction_fraction": reduction,
            "baseline_mean_power": baseline_mean,
            "hypothetical_mean_power": hypothetical_power,
            "estimated_power_difference": (
                baseline_mean - hypothetical_power
            ),
            "is_simulated": True,
            "assumption": (
                "Fixed proportional power reduction; "
                "not a physical cooling model."
            )
        })

    what_if_df = pd.DataFrame(scenarios)

    what_if_df.to_csv(
        OUTPUT_DIR / "what_if_power_comparison.csv",
        index=False
    )

    print("\nWhat-if power comparison:")
    print(what_if_df.to_string(index=False))

    plt.figure(figsize=(8, 4))
    plt.bar(
        what_if_df["scenario"],
        what_if_df["hypothetical_mean_power"]
    )
    plt.xlabel("Hypothetical scenario")
    plt.ylabel("Mean power in source units")
    plt.title("What-if Power Comparison")
    plt.xticks(rotation=20)
    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "what_if_power_comparison.png",
        dpi=180
    )
    plt.close()


# --------------------------------------------------
# 8. STANDARDIZED FUTURE-TEMPERATURE PREDICTION
# --------------------------------------------------

def predict_future_temperature(
    model,
    feature_row,
    asset_id,
    target_metric,
    horizon_minutes,
    model_version="member3-temperature-v1",
    data_quality_status="not_independently_verified"
):
    """
    Generate a standardized prediction record.

    feature_row must contain the trained model's features
    in the same order used during model training.
    """

    prediction = float(model.predict(feature_row)[0])
    prediction_time = pd.Timestamp.now(tz="UTC")

    return {
        "asset_id": str(asset_id),
        "prediction_type": "future_temperature",
        "target_metric": target_metric,
        "horizon_minutes": horizon_minutes,
        "predicted_value": prediction,
        "prediction_timestamp": prediction_time.isoformat(),
        "model_version": model_version,
        "data_quality_status": data_quality_status,
        "is_estimated": True,
        "is_simulated": False,
        "interpretation": "Forecast, not a confirmed failure"
    }


# --------------------------------------------------
# 9. MAIN FAULT-PROPAGATION WORKFLOW
# --------------------------------------------------

def run_fault_propagation(fault_asset_id=None):
    """Run graph tracing, scenario simulation, and optional evaluation."""

    graph, registry, relationships = load_asset_graph()

    if graph.number_of_nodes() == 0:
        print("The asset graph contains no nodes.")
        return None

    if fault_asset_id is None or str(fault_asset_id) not in graph:
        if fault_asset_id is not None:
            print(
                f"Requested source '{fault_asset_id}' was not found."
            )

        fault_asset_id = (
            "M100_NODE_1"
            if "M100_NODE_1" in graph
            else next(iter(graph.nodes))
        )

        print(f"Using source asset: {fault_asset_id}")

    fault_asset_id = str(fault_asset_id)

    # A. Original downstream impact report.
    report = trace_fault(graph, registry, fault_asset_id)

    csv_path = OUTPUT_DIR / "fault_impact_report.csv"
    json_path = OUTPUT_DIR / "fault_impact_report.json"

    report.to_csv(csv_path, index=False)

    result = {
        "fault_source": fault_asset_id,
        "graph_nodes": graph.number_of_nodes(),
        "graph_relationships": graph.number_of_edges(),
        "affected_asset_count": max(len(report) - 1, 0),
        "relationship_count_from_csv": len(relationships),
        "graph_note": (
            "Results represent reachable logical telemetry relationships, "
            "not verified physical fault propagation."
        ),
        "impacts": report.to_dict(orient="records")
    }

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2, default=str)

    print("\nFault propagation analysis completed.")
    print(f"Fault source: {fault_asset_id}")
    print(f"Graph nodes: {graph.number_of_nodes()}")
    print(f"Graph relationships: {graph.number_of_edges()}")
    print(f"Reachable downstream assets: {max(len(report) - 1, 0)}")
    print(f"CSV report: {csv_path}")
    print(f"JSON report: {json_path}")

    if not report.empty:
        print("\nImpact report:")
        print(report.to_string(index=False))

    # B. Controlled propagation scenario.
    scenario_result = run_propagation_scenario(
        graph=graph,
        source_asset_id=fault_asset_id,
        scenario_id="SCN-001",
        scenario_type="temperature_or_fan_anomaly",
        injected_effects={
            "scenario_note": (
                "Illustrative scenario metadata; "
                "not a measured physical effect."
            )
        }
    )

    scenario_path = OUTPUT_DIR / "fault_propagation_scenarios.csv"
    scenario_result.to_csv(scenario_path, index=False)

    print(f"\nScenario report: {scenario_path}")
    print(scenario_result.to_string(index=False))

    # C. Evaluate only if valid ground-truth labels exist.
    evaluate_propagation(scenario_result)

    return report


# --------------------------------------------------
# 10. SCRIPT ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":

    run_fault_propagation("M100_NODE_1")

    run_energy_cooling_analytics()

    run_what_if_analysis()

    print("\nModule 5 fault propagation workflow completed.")
    print(f"All outputs are saved in: {OUTPUT_DIR}")