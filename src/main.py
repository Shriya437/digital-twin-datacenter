
"""Run the complete datacenter digital-twin analysis pipeline.

Run from the project root:
    python -m src.main

Pipeline stages:
1. Load and validate telemetry data.
2. Build the asset registry and dependency graph.
3. Engineer telemetry features.
4. Detect anomalies and rank root-cause hypotheses.
5. Assess potential impact.
6. Generate and evaluate synthetic fault scenarios.
7. Run decision support, maintenance prioritization, simulation,
   safety checks, access control, audit logging and monitoring.
"""

from pathlib import Path
import json

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .data_loader import load_data
from .asset_registry import (
    build_asset_registry,
    build_metric_asset_mapping,
)
from .dependency_graph import (
    build_dependency_graph,
    export_dependency_graph,
)
from .graph_visualization import save_graph_plot
from .feature_engineering import build_telemetry_features
from .anomaly_detector import detect_anomalies
from .root_cause import rank_root_causes
from .impact_analysis import assess_potential_impact
from .fault_scenarios import generate_scenarios
from .evaluation import evaluate_scenarios, save_evaluation_plots

# Integrated decision-support workflow.
from .member4_demo import main as run_decision_support_demo


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"


def make_plot(
    df: pd.DataFrame,
    events: pd.DataFrame,
    path: Path,
) -> dict:
    """Plot processor temperature, anomaly flags and major telemetry gaps."""

    plot_df = df[["timestamp", "p0_vdd_temp"]].copy()

    plot_df["timestamp"] = pd.to_datetime(
        plot_df["timestamp"], utc=True, errors="coerce"
    )
    plot_df["p0_vdd_temp"] = pd.to_numeric(
        plot_df["p0_vdd_temp"], errors="coerce"
    )

    plot_df = (
        plot_df.dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )

    if plot_df.empty:
        raise ValueError(
            "No valid timestamps available for the temperature plot."
        )

    intervals = plot_df["timestamp"].diff().dt.total_seconds()
    positive_intervals = intervals[intervals > 0]

    typical_interval = (
        float(positive_intervals.median())
        if not positive_intervals.empty
        else 20.0
    )

    gap_threshold = max(3.0 * typical_interval, 60.0)

    x_values = []
    y_values = []
    gap_starts = []

    for i, row in plot_df.iterrows():
        if (
            i > 0
            and pd.notna(intervals.iloc[i])
            and intervals.iloc[i] > gap_threshold
        ):
            # Break the plotted line instead of connecting across missing data.
            x_values.append(np.nan)
            y_values.append(np.nan)
            gap_starts.append(row["timestamp"])

        x_values.append(
            mdates.date2num(row["timestamp"].to_pydatetime())
        )
        y_values.append(
            float(row["p0_vdd_temp"])
            if pd.notna(row["p0_vdd_temp"])
            else np.nan
        )

    fig, ax = plt.subplots(figsize=(14, 6))

    ax.plot(
        x_values,
        y_values,
        label="p0_vdd_temp",
        linewidth=1.1,
    )

    required_columns = {
        "timestamp",
        "metric_name",
        "detector",
        "observed_value",
    }

    if (
        events is not None
        and not events.empty
        and required_columns.issubset(events.columns)
    ):
        selected = events[
            (events["metric_name"] == "p0_vdd_temp")
            & (events["detector"] == "robust_z_score")
        ].copy()

        if not selected.empty:
            selected["timestamp"] = pd.to_datetime(
                selected["timestamp"],
                utc=True,
                errors="coerce",
            )
            selected["observed_value"] = pd.to_numeric(
                selected["observed_value"],
                errors="coerce",
            )

            selected = selected.dropna(
                subset=["timestamp", "observed_value"]
            )

            ax.scatter(
                [
                    mdates.date2num(timestamp.to_pydatetime())
                    for timestamp in selected["timestamp"]
                ],
                selected["observed_value"],
                s=24,
                label="Robust Z-score flags",
                zorder=3,
            )

    for i, timestamp in enumerate(gap_starts):
        ax.axvline(
            mdates.date2num(timestamp.to_pydatetime()),
            linestyle="--",
            linewidth=0.8,
            alpha=0.7,
            label="Long telemetry gap" if i == 0 else None,
        )

    ax.set_title(
        "Processor 0 Temperature and Statistical Anomaly Flags"
    )
    ax.set_xlabel("Timestamp (UTC)")
    ax.set_ylabel(
        "Dataset temperature unit (verify source units)"
    )

    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(locator)
    )

    ax.grid(True, alpha=0.2)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)

    return {
        "plot_typical_interval_seconds": typical_interval,
        "plot_gap_break_threshold_seconds": gap_threshold,
        "major_gaps_shown_on_plot": len(gap_starts),
    }


def main():
    """Execute the complete analysis and decision-support workflow."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # Stage 1: Load telemetry and data-quality information.
    # ---------------------------------------------------------
    df, quality, gap_report, summary = load_data(DATA_DIR)

    # ---------------------------------------------------------
    # Stage 2: Asset registry, dependency graph and impact.
    # ---------------------------------------------------------
    registry = build_asset_registry(df, quality)
    graph = build_dependency_graph(registry)

    export_dependency_graph(graph, OUTPUT_DIR)

    build_metric_asset_mapping().to_csv(
        OUTPUT_DIR / "metric_asset_mapping.csv",
        index=False,
    )

    save_graph_plot(
        graph,
        OUTPUT_DIR / "asset_graph.png",
    )

    impact = assess_potential_impact(
        graph,
        "M100_NODE_1",
    )

    impact.to_csv(
        OUTPUT_DIR / "potential_impact_report.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Stage 3: Telemetry feature engineering.
    # ---------------------------------------------------------
    features = build_telemetry_features(df)

    features.to_csv(
        OUTPUT_DIR / "telemetry_features.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Stage 4: Anomaly detection and root-cause hypotheses.
    # ---------------------------------------------------------
    anomalies = detect_anomalies(
        df,
        quality=quality,
        baseline_df=df,
    )

    anomalies.to_csv(
        OUTPUT_DIR / "anomaly_events.csv",
        index=False,
    )

    causes = rank_root_causes(
        df,
        anomalies,
    )

    causes.to_csv(
        OUTPUT_DIR / "root_cause_hypotheses.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # Stage 5: Synthetic fault-scenario evaluation.
    # Synthetic modifications are kept separate from source data.
    # ---------------------------------------------------------
    scenarios = generate_scenarios(df)

    scenario_dir = OUTPUT_DIR / "scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)

    for scenario in scenarios:
        scenario.frame.to_csv(
            scenario_dir / f"{scenario.scenario_id}.csv",
            index=False,
        )

    (
        scenario_events,
        scenario_labels,
        evaluation,
        cause_evaluation,
    ) = evaluate_scenarios(
        df,
        scenarios,
        quality=quality,
    )

    scenario_events.to_csv(
        OUTPUT_DIR / "scenario_detection_events.csv",
        index=False,
    )

    scenario_labels.to_csv(
        OUTPUT_DIR / "synthetic_fault_labels.csv",
        index=False,
    )

    evaluation.to_csv(
        OUTPUT_DIR / "scenario_detection_evaluation.csv",
        index=False,
    )

    cause_evaluation.to_csv(
        OUTPUT_DIR / "scenario_root_cause_evaluation.csv",
        index=False,
    )

    # Summarize root-cause evaluation per synthetic scenario.
    cause_summary_rows = []

    for scenario in scenarios:
        injected_count = int(
            scenario.labels["timestamp"].nunique()
        )

        if not cause_evaluation.empty:
            diagnosed = cause_evaluation[
                cause_evaluation["scenario_id"]
                == scenario.scenario_id
            ]
        else:
            diagnosed = pd.DataFrame()

        diagnosed_count = (
            int(diagnosed["timestamp"].nunique())
            if not diagnosed.empty
            else 0
        )

        cause_summary_rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "expected_cause": scenario.expected_cause,
                "injected_timestamp_count": injected_count,
                "timestamps_with_new_detections_and_ranked_cause":
                    diagnosed_count,
                "diagnosis_coverage": (
                    diagnosed_count / injected_count
                    if injected_count
                    else 0.0
                ),
                "top1_accuracy_conditional_on_diagnosis": (
                    float(diagnosed["top1_correct"].mean())
                    if not diagnosed.empty
                    else np.nan
                ),
                "top3_accuracy_conditional_on_diagnosis": (
                    float(diagnosed["top3_correct"].mean())
                    if not diagnosed.empty
                    else np.nan
                ),
                "evaluation_note": (
                    "Accuracy is conditional on timestamps with newly "
                    "detected evidence; coverage must also be considered."
                ),
            }
        )

    cause_summary = pd.DataFrame(cause_summary_rows)

    cause_summary.to_csv(
        OUTPUT_DIR / "scenario_root_cause_summary.csv",
        index=False,
    )

    save_evaluation_plots(
        evaluation,
        cause_evaluation,
        OUTPUT_DIR,
    )

    # ---------------------------------------------------------
    # Stage 6: Timestamp-gap report and anomaly visualization.
    # ---------------------------------------------------------
    if gap_report is not None:
        gap_report.to_csv(
            OUTPUT_DIR / "timestamp_gap_report_used.csv",
            index=False,
        )

    plot_info = make_plot(
        df,
        anomalies,
        OUTPUT_DIR / "anomaly_detection_plot.png",
    )

    detector_counts = (
        {
            str(name): int(count)
            for name, count in anomalies["detector"].value_counts().items()
        }
        if not anomalies.empty
        else {}
    )

    # ---------------------------------------------------------
    # Stage 7: Consolidate base-pipeline results.
    # These outputs are consumed by the decision-support workflow.
    # ---------------------------------------------------------
    summary.update(
        {
            "registry_nodes": int(graph.number_of_nodes()),
            "registry_relationships": int(graph.number_of_edges()),
            "anomaly_event_rows": int(len(anomalies)),
            "root_cause_hypothesis_rows": int(len(causes)),
            "anomaly_counts_by_detector": detector_counts,
            "synthetic_scenarios_evaluated": int(len(scenarios)),
            "scenario_detection_evaluation_rows": int(
                len(evaluation)
            ),
            "scenario_root_cause_evaluation_rows": int(
                len(cause_evaluation)
            ),
            "scenario_root_cause_summary_rows": int(
                len(cause_summary)
            ),
            "recomputed_major_gaps_in_report": (
                int(gap_report["is_major_gap"].sum())
                if (
                    gap_report is not None
                    and "is_major_gap" in gap_report.columns
                )
                else 0
            ),
            "graph_scope_warning": (
                "The graph represents dataset-backed logical telemetry "
                "associations; physical cooling and power topology "
                "has not been verified."
            ),
            "ml_scope_warning": (
                "Anomaly detections are candidates, not confirmed failures. "
                "Synthetic scenario metrics are not real-world accuracy "
                "estimates."
            ),
            **plot_info,
        }
    )

    # ---------------------------------------------------------
    # Stage 8: Decision support and safety workflow.
    # Runs only after the required base-pipeline files exist.
    # ---------------------------------------------------------
    print("\nRunning decision-support and safety workflow...")

    run_decision_support_demo()

    integration_output_dir = OUTPUT_DIR / "member4"

    expected_integration_outputs = [
        "alert_context.json",
        "data_quality.json",
        "maintenance_tasks.csv",
        "model_monitoring.json",
        "safety_decisions.json",
        "scenario_comparisons.json",
    ]

    missing_outputs = [
        filename
        for filename in expected_integration_outputs
        if not (integration_output_dir / filename).is_file()
    ]

    if missing_outputs:
        raise RuntimeError(
            "Decision-support workflow did not generate all expected "
            f"outputs. Missing: {', '.join(missing_outputs)}"
        )

    summary["decision_support"] = {
        "status": "completed",
        "output_directory": str(integration_output_dir),
        "expected_output_files": expected_integration_outputs,
        "equipment_actions_executed": False,
    }

    # ---------------------------------------------------------
    # Stage 9: Save the final consolidated run summary.
    # ---------------------------------------------------------
    summary_path = OUTPUT_DIR / "run_summary.json"

    with open(summary_path, "w", encoding="utf-8") as file:
        json.dump(
            summary,
            file,
            indent=2,
            default=str,
        )

    # ---------------------------------------------------------
    # Final run report.
    # ---------------------------------------------------------
    print("\nComplete datacenter digital-twin pipeline finished.")
    print(f"Input rows: {summary['rows_loaded']}")
    print(
        f"Registry nodes: {summary['registry_nodes']}; "
        f"relationships: {summary['registry_relationships']}"
    )
    print(f"Anomaly event rows: {summary['anomaly_event_rows']}")
    print(
        "Root-cause hypothesis rows: "
        f"{summary['root_cause_hypothesis_rows']}"
    )
    print(
        "Synthetic scenarios evaluated: "
        f"{summary['synthetic_scenarios_evaluated']}"
    )
    print(
        "Long gaps broken in plot: "
        f"{summary['major_gaps_shown_on_plot']}"
    )
    print("Decision-support workflow: completed")
    print(f"Run summary: {summary_path}")
    print(f"All outputs: {OUTPUT_DIR}")
    print(
        "Note: anomaly candidates are not confirmed failures; "
        "synthetic evaluation does not establish real-world accuracy."
    )
    print(
        "Safety note: recommendations and simulated scenarios do not "
        "execute equipment-control actions."
    )


if __name__ == "__main__":
    main()
