"""Run the complete Member 2 pipeline from the project root.

Command: python -m src.main
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from .data_loader import load_data, METRICS
from .asset_registry import build_asset_registry, build_metric_asset_mapping
from .dependency_graph import build_dependency_graph, export_dependency_graph, related_assets
from .graph_visualization import save_graph_plot
from .feature_engineering import build_telemetry_features
from .anomaly_detector import detect_anomalies
from .root_cause import rank_root_causes
from .impact_analysis import assess_potential_impact
from .fault_scenarios import generate_scenarios
from .evaluation import evaluate_scenarios, save_evaluation_plots

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"


def make_plot(df: pd.DataFrame, events: pd.DataFrame, path: Path):
    plot_df = df[["timestamp", "p0_vdd_temp"]].copy()
    plot_df["timestamp"] = pd.to_datetime(plot_df["timestamp"], utc=True, errors="coerce")
    plot_df["p0_vdd_temp"] = pd.to_numeric(plot_df["p0_vdd_temp"], errors="coerce")
    plot_df = plot_df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    if plot_df.empty:
        raise ValueError("No valid timestamps available for the temperature plot")
    intervals = plot_df["timestamp"].diff().dt.total_seconds()
    positive = intervals[intervals > 0]
    typical = float(positive.median()) if not positive.empty else 20.0
    threshold = max(3.0 * typical, 60.0)
    x, y, gap_starts = [], [], []
    for i, row in plot_df.iterrows():
        if i > 0 and pd.notna(intervals.iloc[i]) and intervals.iloc[i] > threshold:
            x.append(np.nan); y.append(np.nan); gap_starts.append(row["timestamp"])
        x.append(mdates.date2num(row["timestamp"].to_pydatetime()))
        y.append(float(row["p0_vdd_temp"]) if pd.notna(row["p0_vdd_temp"]) else np.nan)
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(x, y, label="p0_vdd_temp", linewidth=1.1)
    if events is not None and not events.empty and {"timestamp", "metric_name", "detector", "observed_value"}.issubset(events.columns):
        selected = events[(events["metric_name"] == "p0_vdd_temp") & (events["detector"] == "robust_z_score")].copy()
        if not selected.empty:
            selected["timestamp"] = pd.to_datetime(selected["timestamp"], utc=True, errors="coerce")
            selected["observed_value"] = pd.to_numeric(selected["observed_value"], errors="coerce")
            selected = selected.dropna(subset=["timestamp", "observed_value"])
            ax.scatter([mdates.date2num(t.to_pydatetime()) for t in selected["timestamp"]],
                       selected["observed_value"], s=24, label="Robust Z-score flags", zorder=3)
    for i, ts in enumerate(gap_starts):
        ax.axvline(mdates.date2num(ts.to_pydatetime()), linestyle="--", linewidth=0.8,
                   alpha=0.7, label="Long telemetry gap" if i == 0 else None)
    ax.set_title("Processor 0 Temperature and Statistical Anomaly Flags")
    ax.set_xlabel("Timestamp (UTC)")
    ax.set_ylabel("Dataset temperature unit (verify source units)")
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.grid(True, alpha=0.2); ax.legend(); fig.autofmt_xdate(); fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return {"plot_typical_interval_seconds": typical,
            "plot_gap_break_threshold_seconds": threshold,
            "major_gaps_shown_on_plot": len(gap_starts)}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df, quality, gap_report, summary = load_data(DATA_DIR)

    # Module 1: registry, logical graph, mapping and graph queries.
    registry = build_asset_registry(df, quality)
    graph = build_dependency_graph(registry)
    export_dependency_graph(graph, OUTPUT_DIR)
    build_metric_asset_mapping().to_csv(OUTPUT_DIR / "metric_asset_mapping.csv", index=False)
    save_graph_plot(graph, OUTPUT_DIR / "asset_graph.png")
    impact = assess_potential_impact(graph, "M100_NODE_1")
    impact.to_csv(OUTPUT_DIR / "potential_impact_report.csv", index=False)

    # Data exploration / feature engineering: preserve the raw input unchanged.
    features = build_telemetry_features(df)
    features.to_csv(OUTPUT_DIR / "telemetry_features.csv", index=False)

    # Module 4: base-data anomaly screening and explainable hypotheses.
    anomalies = detect_anomalies(df, quality=quality, baseline_df=df)
    anomalies.to_csv(OUTPUT_DIR / "anomaly_events.csv", index=False)
    causes = rank_root_causes(df, anomalies)
    causes.to_csv(OUTPUT_DIR / "root_cause_hypotheses.csv", index=False)

    # Controlled evaluation: faults are generated in separate copies, never in the source CSV.
    scenarios = generate_scenarios(df)
    scenario_dir = OUTPUT_DIR / "scenarios"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        scenario.frame.to_csv(scenario_dir / f"{scenario.scenario_id}.csv", index=False)
    scenario_events, scenario_labels, evaluation, cause_evaluation = evaluate_scenarios(
        df, scenarios, quality=quality
    )
    scenario_events.to_csv(OUTPUT_DIR / "scenario_detection_events.csv", index=False)
    scenario_labels.to_csv(OUTPUT_DIR / "synthetic_fault_labels.csv", index=False)
    evaluation.to_csv(OUTPUT_DIR / "scenario_detection_evaluation.csv", index=False)
    cause_evaluation.to_csv(OUTPUT_DIR / "scenario_root_cause_evaluation.csv", index=False)
    cause_summary_rows = []
    for scenario in scenarios:
        injected_count = int(scenario.labels["timestamp"].nunique())
        diagnosed = cause_evaluation[cause_evaluation["scenario_id"] == scenario.scenario_id] if not cause_evaluation.empty else pd.DataFrame()
        diagnosed_count = int(diagnosed["timestamp"].nunique()) if not diagnosed.empty else 0
        cause_summary_rows.append({
            "scenario_id": scenario.scenario_id,
            "expected_cause": scenario.expected_cause,
            "injected_timestamp_count": injected_count,
            "timestamps_with_new_detections_and_ranked_cause": diagnosed_count,
            "diagnosis_coverage": diagnosed_count / injected_count if injected_count else 0.0,
            "top1_accuracy_conditional_on_diagnosis": float(diagnosed["top1_correct"].mean()) if not diagnosed.empty else np.nan,
            "top3_accuracy_conditional_on_diagnosis": float(diagnosed["top3_correct"].mean()) if not diagnosed.empty else np.nan,
            "evaluation_note": "Accuracy is conditional on timestamps with newly detected evidence; coverage must be considered alongside it.",
        })
    cause_summary = pd.DataFrame(cause_summary_rows)
    cause_summary.to_csv(OUTPUT_DIR / "scenario_root_cause_summary.csv", index=False)
    save_evaluation_plots(evaluation, cause_evaluation, OUTPUT_DIR)

    if gap_report is not None:
        gap_report.to_csv(OUTPUT_DIR / "timestamp_gap_report_used.csv", index=False)
    plot_info = make_plot(df, anomalies, OUTPUT_DIR / "anomaly_detection_plot.png")
    detector_counts = ({str(k): int(v) for k, v in anomalies["detector"].value_counts().items()}
                       if not anomalies.empty else {})
    summary.update({
        "registry_nodes": int(graph.number_of_nodes()),
        "registry_relationships": int(graph.number_of_edges()),
        "anomaly_event_rows": int(len(anomalies)),
        "root_cause_hypothesis_rows": int(len(causes)),
        "anomaly_counts_by_detector": detector_counts,
        "synthetic_scenarios_evaluated": int(len(scenarios)),
        "scenario_detection_evaluation_rows": int(len(evaluation)),
        "scenario_root_cause_evaluation_rows": int(len(cause_evaluation)),
        "scenario_root_cause_summary_rows": int(len(cause_summary)),
        "recomputed_major_gaps_in_report": int(gap_report["is_major_gap"].sum()) if gap_report is not None and "is_major_gap" in gap_report else 0,
        "graph_scope_warning": "Graph represents dataset-backed logical telemetry associations only; physical cooling/power topology is not verified.",
        "ml_scope_warning": "Unsupervised detections are anomaly candidates, not confirmed failures. Synthetic scenario metrics are not real-world accuracy estimates.",
        **plot_info,
    })
    with open(OUTPUT_DIR / "run_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\nMember 2 pipeline completed.")
    print(f"Input rows: {summary['rows_loaded']}")
    print(f"Registry nodes: {summary['registry_nodes']}; relationships: {summary['registry_relationships']}")
    print(f"Base anomaly event rows: {summary['anomaly_event_rows']}")
    print(f"Root-cause hypothesis rows: {summary['root_cause_hypothesis_rows']}")
    print(f"Synthetic scenarios evaluated: {summary['synthetic_scenarios_evaluated']}")
    print(f"Long gaps broken in plot: {summary['major_gaps_shown_on_plot']}")
    print(f"Outputs: {OUTPUT_DIR}")
    print("Important: synthetic evaluation measures response to injected scenarios only; it is not real-world fault accuracy.")

if __name__ == "__main__":
    main()
