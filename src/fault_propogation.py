import sys
from pathlib import Path
import json

import joblib
import numpy as np
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt

from sklearn.metrics import precision_score, recall_score, f1_score

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import generate_scenarios from fault_scenarios
try:
    from src.fault_scenarios import generate_scenarios
except Exception:
    try:
        from fault_scenarios import generate_scenarios
    except Exception as e:
        print(f"Warning: could not import generate_scenarios: {e}")
        generate_scenarios = None

# Import causal features from labeling if available
LABELING_DIR = ROOT_DIR / "data" / "m100_labeling" / "ml_labeling"
if str(LABELING_DIR) not in sys.path:
    sys.path.insert(0, str(LABELING_DIR))
try:
    import labeling as L
except Exception:
    L = None

# Metric to asset ID mapping
METRIC_TO_ASSET_ID = {
    "p0_vdd_temp": "M100_NODE_1::p0_vdd_temp",
    "p1_vdd_temp": "M100_NODE_1::p1_vdd_temp",
    "fan0_0": "M100_NODE_1::fan0_0",
    "fan1_0": "M100_NODE_1::fan1_0",
    "total_power": "M100_NODE_1::total_power",
    "ps0_input_power": "M100_NODE_1::ps0_input_power",
    "ps1_input_power": "M100_NODE_1::ps1_input_power",
    "ambient": "M100_NODE_1::ambient",
}

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

def trace_cascading_fault(graph, registry, fault_asset_id, scenario_type=None):
    """
    Find cascading assets reachable across the asset graph topology.
    
    Traverses hierarchically from metric leaf through host node (M100_NODE_1)
    and propagates outward across physical/telemetric subsystem domains:
      Stage 0: Fault Origin (Injected Metric / Asset)
      Stage 1: Host Node Chassis (Host Controller & Node Plane)
      Stage 2: Primary Subsystem Coupling (Direct thermal/cooling/power reaction)
      Stage 3: Cross-Domain Blast Radius (Downstream secondary effects, e.g. throttling/power shift)
    """
    fault_asset_id = str(fault_asset_id)
    if fault_asset_id not in graph:
        raise ValueError(f"Asset '{fault_asset_id}' was not found in the graph.")

    registry_by_id = registry.set_index("asset_id").to_dict("index")

    # If the root node itself is the fault origin:
    if fault_asset_id == "M100_NODE_1":
        descendants = sorted(list(graph.successors(fault_asset_id)))
        affected_assets = [{
            "fault_source": fault_asset_id,
            "asset_id": fault_asset_id,
            "display_name": registry_by_id.get(fault_asset_id, {}).get("display_name", "M100 Node 1"),
            "asset_type": registry_by_id.get(fault_asset_id, {}).get("asset_type", "monitored_node"),
            "impact_depth": 0,
            "cascade_stage": 0,
            "stage_label": "Stage 0: Host Node Origin",
            "impact_category": "fault_source",
            "relationship_path": fault_asset_id,
            "physical_impact_verified": False,
        }]
        for child in descendants:
            meta = registry_by_id.get(child, {})
            affected_assets.append({
                "fault_source": fault_asset_id,
                "asset_id": child,
                "display_name": meta.get("display_name", child.split("::")[-1]),
                "asset_type": meta.get("asset_type", "metric"),
                "impact_depth": 1,
                "cascade_stage": 1,
                "stage_label": "Stage 1: Monitored Telemetry",
                "impact_category": "directly_reachable",
                "relationship_path": f"{fault_asset_id} -> {child}",
                "physical_impact_verified": False,
            })
        cascade_stages = [
            {"stage": 0, "stage_label": "Stage 0: Node Origin", "assets": [fault_asset_id], "description": "Host chassis failure event"},
            {"stage": 1, "stage_label": "Stage 1: Monitored Telemetry", "assets": descendants, "description": "Direct child telemetry metrics"},
        ]
        cascading_path_str = f"M100_NODE_1 ➔ ({len(descendants)} Monitored Telemetry Channels)"
        return pd.DataFrame(affected_assets), cascade_stages, cascading_path_str

    # Leaf metric origin: traverse up to host node, then cascade across domains
    parent_nodes = list(graph.predecessors(fault_asset_id))
    host_node = parent_nodes[0] if parent_nodes else "M100_NODE_1"
    
    # Siblings connected to this host node in asset graph
    siblings = [n for n in graph.successors(host_node) if n != fault_asset_id] if host_node in graph else []

    def get_domain(aid):
        low = aid.lower()
        if "fan" in low:
            return "cooling"
        elif "temp" in low or "ambient" in low:
            return "thermal"
        elif "power" in low or "ps" in low:
            return "power"
        return "system"

    source_domain = get_domain(fault_asset_id)

    stage0_assets = [fault_asset_id]
    stage1_assets = [host_node] if host_node in graph else []
    
    if source_domain == "cooling":
        # Fan degradation: heats up thermal sensors and ramps peer fan
        stage2_assets = [s for s in siblings if get_domain(s) in ("thermal", "cooling")]
        # Thermal throttling causes power drop
        stage3_assets = [s for s in siblings if get_domain(s) == "power"]
        stage2_desc = "Airflow deficit creates heatsink thermal accumulation and triggers peer fan ramp"
        stage3_desc = "Thermal safety throttle initiates CPU frequency drop and PSU load fluctuation"
    elif source_domain == "thermal":
        # Temperature spike / drift: surges cooling fans and heats peer socket
        stage2_assets = [s for s in siblings if get_domain(s) in ("cooling", "thermal")]
        # Throttling lowers power
        stage3_assets = [s for s in siblings if get_domain(s) == "power"]
        stage2_desc = "Thermal gradient activates cooling fan acceleration and heats neighboring socket"
        stage3_desc = "Emergency CPU clock throttling lowers socket power draw and shifts PSU demand"
    elif source_domain == "power":
        # Power spike: propagates across PSUs and socket power rails
        stage2_assets = [s for s in siblings if get_domain(s) == "power"]
        # High power causes resistive Joule heating and fan ramp
        stage3_assets = [s for s in siblings if get_domain(s) in ("thermal", "cooling")]
        stage2_desc = "High transient current propagates through PSU rails and CPU voltage regulators"
        stage3_desc = "Joule resistive heating escalates die temperature and engages cooling fans"
    else:
        stage2_assets = [s for s in siblings if get_domain(s) == "thermal"]
        stage3_assets = [s for s in siblings if s not in stage2_assets]
        stage2_desc = "Primary domain telemetric coupling"
        stage3_desc = "Secondary system blast radius"

    affected_assets = []
    
    def add_row(aid, depth, stage, stage_label, category, path_str):
        meta = registry_by_id.get(aid, {})
        affected_assets.append({
            "fault_source": fault_asset_id,
            "asset_id": aid,
            "display_name": meta.get("display_name", aid.split("::")[-1]),
            "asset_type": meta.get("asset_type", "unknown"),
            "impact_depth": depth,
            "cascade_stage": stage,
            "stage_label": stage_label,
            "impact_category": category,
            "relationship_path": path_str,
            "physical_impact_verified": False,
        })

    # Stage 0:
    for a in stage0_assets:
        add_row(a, 0, 0, "Stage 0: Fault Origin", "fault_source", a)

    # Stage 1:
    for a in stage1_assets:
        add_row(a, 1, 1, "Stage 1: Host Node", "host_node_impact", f"{fault_asset_id} -> {a}")

    # Stage 2:
    for a in stage2_assets:
        add_row(a, 2, 2, "Stage 2: Primary Subsystem", "primary_cascade", f"{fault_asset_id} -> {host_node} -> {a}")

    # Stage 3:
    for a in stage3_assets:
        add_row(a, 3, 3, "Stage 3: Cross-Domain Blast Radius", "secondary_cascade", f"{fault_asset_id} -> {host_node} -> ... -> {a}")

    short_src = fault_asset_id.split("::")[-1]
    stage2_names = [a.split("::")[-1] for a in stage2_assets]
    stage3_names = [a.split("::")[-1] for a in stage3_assets]
    
    cascading_path_str = f"{short_src} ➔ {host_node} ➔ ({', '.join(stage2_names[:2])}{'...' if len(stage2_names) > 2 else ''}) ➔ ({', '.join(stage3_names[:2])}{'...' if len(stage3_names) > 2 else ''})"

    cascade_stages = [
        {
            "stage": 0,
            "stage_label": "Stage 0: Fault Origin",
            "assets": [fault_asset_id],
            "description": f"Directly perturbed asset ({short_src}) in simulated scenario"
        },
        {
            "stage": 1,
            "stage_label": "Stage 1: Host Node",
            "assets": stage1_assets,
            "description": "Host node chassis controller receives telemetry disruption"
        },
        {
            "stage": 2,
            "stage_label": "Stage 2: Primary Subsystem Coupling",
            "assets": stage2_assets,
            "description": stage2_desc
        },
        {
            "stage": 3,
            "stage_label": "Stage 3: Cross-Domain Blast Radius",
            "assets": stage3_assets,
            "description": stage3_desc
        }
    ]

    return pd.DataFrame(affected_assets), cascade_stages, cascading_path_str


def trace_fault(graph, registry, fault_asset_id):
    """Find assets reachable downstream and cascading from a fault source."""
    df, _, _ = trace_cascading_fault(graph, registry, fault_asset_id)
    return df


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

    # ---------------- STEP 8.2: PUE SAFEGUARD ----------------
    pue_report = pd.DataFrame([{
        "pue_calculated": False,
        "reason": (
            "A single-node telemetry CSV does not by itself "
            "establish total facility energy and complete IT "
            "equipment energy over comparable intervals."
        ),
        "required_facility_energy": "Total facility energy over reporting interval (kWh)",
        "required_it_energy": "IT equipment energy over the same reporting interval (kWh)",
        "formula": "PUE = Total facility energy / IT equipment energy",
        "scope_guidance": "Do not report a PUE value from total_power alone."
    }])
    pue_report.to_csv(OUTPUT_DIR / "pue_requirements.csv", index=False)
    print("\nPUE requirements saved: do not claim PUE without facility-wide measurements.")

    # ---------------- STEP 9.1: THERMAL-DIFFERENCE INDICATOR ----------------
    if {"p0_vdd_temp", "p1_vdd_temp"}.issubset(df.columns):
        df["processor_temp_difference"] = (
            df["p0_vdd_temp"] - df["p1_vdd_temp"]
        )

        plt.figure(figsize=(12, 4))
        plt.plot(
            df["timestamp"],
            df["processor_temp_difference"]
        )

        plt.xlabel("Timestamp")
        plt.ylabel("Temperature difference (unit to verify)")
        plt.title("Difference Between Processor Temperature Metrics")
        plt.tight_layout()

        plt.savefig(
            OUTPUT_DIR / "processor_temperature_difference.png",
            dpi=180
        )
        plt.close()
        print("Saved processor_temperature_difference.png")

    # ---------------- STEP 9.2: FAN-RELATED READINGS ----------------
    for metric in ["fan0_0", "fan1_0"]:
        if metric not in df.columns:
            continue

        plt.figure(figsize=(12, 4))
        plt.plot(df["timestamp"], df[metric])
        plt.xlabel("Timestamp")
        plt.ylabel(f"{metric} (unit to verify)")
        plt.title(f"Fan-Related Telemetry: {metric}")
        plt.tight_layout()

        plt.savefig(
            OUTPUT_DIR / f"{metric}_trend.png",
            dpi=180
        )
        plt.close()
        print(f"Saved {metric}_trend.png")

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

    # B. Connected Fault Scenarios & Multiclass Classifier Evaluation
    # Connects src.fault_scenarios (5 scenarios) to graph propagation and ML classifier predictions.
    # Keeps Scenario Injection, Classifier Predictions, and Graph Reachability distinct.
    scenario_rows = []
    integrated_workflow = []

    # Attempt to load trained multiclass classifier
    mc_model = None
    mc_model_path = ROOT_DIR / "outputs" / "multiclass_fault_classifier.joblib"
    if not mc_model_path.exists():
        mc_model_path = ROOT_DIR / "data" / "m100_labeling" / "outputs" / "labeled_dataset" / "multiclass_fault_classifier.joblib"
    if mc_model_path.exists():
        try:
            mc_model = joblib.load(mc_model_path)
        except Exception:
            mc_model = None

    if generate_scenarios is not None and TELEMETRY_FILE.exists():
        raw_df = pd.read_csv(TELEMETRY_FILE)
        scenarios = generate_scenarios(raw_df)
        print(f"\nEvaluating {len(scenarios)} connected fault scenarios from fault_scenarios.py...")

        for sc in scenarios:
            metric = sc.labels["affected_metric"].iloc[0] if "affected_metric" in sc.labels.columns else "p0_vdd_temp"
            source_asset = METRIC_TO_ASSET_ID.get(metric, fault_asset_id)
            if source_asset not in graph:
                source_asset = fault_asset_id

            injected_mask = sc.frame["injected_fault"] == True
            injected_count = int(injected_mask.sum())

            # 1. Scenario Injection Metadata (Strictly Synthetic)
            injection_info = {
                "scenario_id": sc.scenario_id,
                "scenario_type": sc.scenario_type,
                "expected_cause": sc.expected_cause,
                "affected_metric": metric,
                "source_asset_id": source_asset,
                "injected_row_count": injected_count,
                "is_simulated": True,
                "data_origin": "synthetic",
                "injection_details": "Controlled synthetic perturbation for validation; source data untouched."
            }

            # 2. Classifier Prediction on Injected Rows (ML Model Inference)
            classifier_info = {
                "model_name": "RandomForest" if mc_model is not None else "RuleBaseline",
                "predicted_class": "unclassified",
                "confidence": 0.0,
                "class_distribution": {},
                "model_status": "evaluated" if mc_model is not None else "model_pending"
            }

            if mc_model is not None and L is not None and injected_count > 0:
                try:
                    seg = pd.Series(0, index=sc.frame.index)
                    feats = L.causal_features(sc.frame, seg).drop(columns=["segment_id", "pos_in_segment"])
                    inj_feats = feats[injected_mask]
                    preds = mc_model.predict(inj_feats)
                    probs = mc_model.predict_proba(inj_feats)
                    top_pred = pd.Series(preds).mode().iloc[0] if len(preds) > 0 else "unknown"
                    avg_conf = float(np.max(probs, axis=1).mean()) if len(probs) > 0 else 0.0
                    counts = {str(k): int(v) for k, v in pd.Series(preds).value_counts().items()}
                    classifier_info.update({
                        "predicted_class": top_pred,
                        "confidence": round(avg_conf, 4),
                        "class_distribution": counts,
                    })
                except Exception as e:
                    classifier_info["prediction_note"] = str(e)
            else:
                # Rule-based fallback expectation
                classifier_info.update({
                    "predicted_class": "thermal_anomaly" if "temp" in metric else "fan_performance_anomaly" if "fan" in metric else "power_anomaly",
                    "confidence": 0.75,
                })

            # 3. Graph-based Propagation Results (Topological Reachability & Cascading Stages)
            target_asset = source_asset if source_asset in graph else fault_asset_id
            reachable_impact, cascade_stages, cascading_path_str = trace_cascading_fault(
                graph, registry, target_asset, scenario_type=sc.scenario_type
            )
            reach_list = reachable_impact.to_dict(orient="records")

            propagation_info = {
                "source_asset_id": source_asset,
                "asset_graph_referenced": True,
                "asset_graph_source": "outputs/asset_graph.json",
                "reachable_asset_count": len(reach_list),
                "max_impact_depth": int(reachable_impact["impact_depth"].max()) if not reachable_impact.empty else 0,
                "cascading_path": cascading_path_str,
                "cascade_stages": cascade_stages,
                "impacted_assets": [r.get("asset_id") for r in reach_list],
                "safeguard_warning": "Logical dependency graph reachability; not a physical failure propagation model."
            }

            integrated_workflow.append({
                "scenario_id": sc.scenario_id,
                "scenario_injection": injection_info,
                "classifier_prediction": classifier_info,
                "graph_propagation": propagation_info,
            })

            # Tabular rows for fault_propagation_scenarios.csv
            for _, imp_row in reachable_impact.iterrows():
                scenario_rows.append({
                    "scenario_id": sc.scenario_id,
                    "scenario_type": sc.scenario_type,
                    "affected_metric": metric,
                    "source_asset_id": source_asset,
                    "affected_asset_id": imp_row.get("asset_id"),
                    "impact_depth": imp_row.get("impact_depth", 0),
                    "impact_category": imp_row.get("impact_category", "reachable"),
                    "predicted_class": classifier_info["predicted_class"],
                    "prediction_confidence": classifier_info["confidence"],
                    "relationship_path": imp_row.get("relationship_path", ""),
                    "is_simulated": True,
                    "data_origin": "synthetic",
                })

    if scenario_rows:
        scenario_df = pd.DataFrame(scenario_rows)
    else:
        # Fallback if scenario generation was not available
        scenario_df = run_propagation_scenario(
            graph=graph,
            source_asset_id=fault_asset_id,
            scenario_id="SCN-001",
            scenario_type="temperature_or_fan_anomaly",
            injected_effects={"scenario_note": "Fallback single scenario"}
        )

    scenario_path = OUTPUT_DIR / "fault_propagation_scenarios.csv"
    scenario_df.to_csv(scenario_path, index=False)
    print(f"\nConnected scenario report ({len(scenario_df)} rows) saved to: {scenario_path}")

    # Save integrated workflow JSON keeping the 3 domains strictly distinct
    workflow_path = OUTPUT_DIR / "integrated_fault_workflow.json"
    with open(workflow_path, "w", encoding="utf-8") as wf:
        json.dump({
            "generated_scenarios_evaluated": len(integrated_workflow),
            "methodology": "Strict separation between: (1) Synthetic Scenario Injection, (2) ML Classifier Predictions, and (3) Topological Graph Reachability.",
            "scenarios": integrated_workflow
        }, wf, indent=2, default=str)
    print(f"Integrated fault workflow saved to: {workflow_path}")

    matrix_path = OUTPUT_DIR / "scenario_impact_matrix.json"
    with open(matrix_path, "w", encoding="utf-8") as mf:
        json.dump(integrated_workflow, mf, indent=2, default=str)

    # C. Evaluate only if valid ground-truth labels exist.
    evaluate_propagation(scenario_df)

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