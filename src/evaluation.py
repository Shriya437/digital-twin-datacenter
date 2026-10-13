"""Counterfactual evaluation for controlled synthetic fault scenarios.

All reported metrics are synthetic-test metrics. A detector is credited only when
its score crosses threshold and is new or materially stronger than the same
observation in the unmodified baseline.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .anomaly_detector import detect_anomalies
from .root_cause import rank_root_causes

METHODS = ["robust_z_score", "rolling_robust_z_score", "isolation_forest", "pca_reconstruction"]
UNIVARIATE = {"robust_z_score", "rolling_robust_z_score"}


def _event_key(row):
    ts = pd.to_datetime(row["timestamp"], utc=True, errors="coerce")
    return (ts, str(row["metric_name"])) if row["detector"] in UNIVARIATE else (ts, "MULTIVARIATE")


def _new_or_strengthened(events, baseline_events):
    """Mark newly flagged or materially increased scores versus the same baseline row."""
    out = events.copy()
    baseline_scores = {}
    if baseline_events is not None and not baseline_events.empty:
        for _, row in baseline_events.iterrows():
            key = (row["detector"], *_event_key(row))
            baseline_scores[key] = float(row["anomaly_score"])
    flags = []
    for _, row in out.iterrows():
        key = (row["detector"], *_event_key(row))
        score = float(row["anomaly_score"])
        previous = baseline_scores.get(key)
        # Existing baseline flags are not automatically credited to a fault.
        # A 10% score rise (or a small absolute floor) indicates scenario influence.
        if previous is None:
            flags.append(True)
        else:
            margin = max(0.02, 0.10 * abs(previous))
            flags.append(score > previous + margin)
    out["new_vs_original_baseline"] = flags
    return out


def evaluate_scenarios(base_df: pd.DataFrame, scenarios, quality: pd.DataFrame | None = None,
                       contamination: float = 0.02, random_state: int = 42):
    detection_rows, label_rows, summary_rows, cause_eval_rows = [], [], [], []
    baseline_events = detect_anomalies(base_df, quality=quality, contamination=contamination,
                                       random_state=random_state, baseline_df=base_df)
    for scenario in scenarios:
        scenario_df = scenario.frame.copy()
        events = detect_anomalies(scenario_df, quality=quality, contamination=contamination,
                                  random_state=random_state, baseline_df=base_df)
        if not events.empty:
            events["scenario_id"] = scenario.scenario_id
            events = _new_or_strengthened(events, baseline_events)
            detection_rows.append(events)
        labels = scenario.labels.copy()
        label_rows.append(labels)
        all_ts = pd.to_datetime(scenario_df["timestamp"], utc=True)
        injected_ts = pd.to_datetime(labels["timestamp"], utc=True).drop_duplicates().sort_values()
        injected_set = set(injected_ts)
        first_injected = injected_ts.iloc[0] if not injected_ts.empty else pd.NaT
        true_row = all_ts.isin(injected_set).to_numpy()
        scenario_events = events if not events.empty else pd.DataFrame(columns=["timestamp", "detector", "metric_name", "new_vs_original_baseline"])
        for method in METHODS:
            if scenario_events.empty:
                method_events = scenario_events
            else:
                method_events = scenario_events[(scenario_events["detector"] == method) & scenario_events["new_vs_original_baseline"].astype(bool)]
            pred_ts = set(pd.to_datetime(method_events["timestamp"], utc=True).dropna()) if not method_events.empty else set()
            before_mask = all_ts < first_injected if pd.notna(first_injected) else pd.Series(False, index=all_ts.index)
            false_before = int(sum(t in pred_ts for t in all_ts[before_mask.to_numpy()]))
            detected_after = sorted(t for t in pred_ts if pd.notna(first_injected) and t >= first_injected)
            delay = (detected_after[0] - first_injected).total_seconds() if detected_after else np.nan
            if method in UNIVARIATE:
                true_pairs = set(zip(pd.to_datetime(labels["timestamp"], utc=True), labels["affected_metric"].astype(str)))
                pred_pairs = set(zip(pd.to_datetime(method_events["timestamp"], utc=True), method_events["metric_name"].astype(str))) if not method_events.empty else set()
                tp = len(true_pairs & pred_pairs)
                precision = tp / len(pred_pairs) if pred_pairs else 0.0
                recall = tp / len(true_pairs) if true_pairs else 0.0
                f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                unit, predicted_count, false_count = "metric_timestamp", len(pred_pairs), len(pred_pairs - true_pairs)
            else:
                pred_row = all_ts.isin(pred_ts).to_numpy()
                tp = int((pred_row & true_row).sum())
                precision = tp / int(pred_row.sum()) if pred_row.sum() else 0.0
                recall = tp / int(true_row.sum()) if true_row.sum() else 0.0
                f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                unit, predicted_count, false_count = "timestamp", int(pred_row.sum()), int((pred_row & ~true_row).sum())
            summary_rows.append({
                "scenario_id": scenario.scenario_id, "scenario_type": scenario.scenario_type,
                "expected_cause": scenario.expected_cause, "detector": method,
                "evaluation_unit": unit, "precision": float(precision), "recall": float(recall), "f1": float(f1),
                "injected_timestamp_count": int(true_row.sum()),
                "predicted_timestamp_or_metric_count": int(predicted_count), "false_alarm_count": int(false_count),
                "false_alarm_count_before_injection": false_before, "detection_delay_seconds": delay,
                "evaluation_note": "Synthetic counterfactual test only; new or materially strengthened scores versus original baseline; not real-world accuracy",
            })
        if not scenario_events.empty:
            new_events = scenario_events[scenario_events["new_vs_original_baseline"].astype(bool)].copy()
            causes = rank_root_causes(scenario_df, new_events, baseline_df=base_df)
            if not causes.empty:
                causes = causes[pd.to_datetime(causes["timestamp"], utc=True).isin(injected_set)]
                for ts, group in causes.groupby("timestamp"):
                    ranked = group.sort_values(["rank", "ranking_score"], ascending=[True, False])
                    ranked_causes = ranked["candidate_cause"].astype(str).tolist()
                    cause_eval_rows.append({
                        "scenario_id": scenario.scenario_id, "timestamp": ts,
                        "expected_cause": scenario.expected_cause,
                        "candidate_cause": ranked_causes[0] if ranked_causes else "unknown_or_insufficient_evidence",
                        "rank": 1,
                        "top1_correct": bool(ranked_causes and ranked_causes[0] == scenario.expected_cause),
                        "top3_correct": bool(scenario.expected_cause in ranked_causes[:3]),
                        "evaluation_note": "Synthetic labels; heuristic ranking; conditional on a new/strengthened detection",
                    })
    detection = pd.concat(detection_rows, ignore_index=True) if detection_rows else pd.DataFrame()
    labels = pd.concat(label_rows, ignore_index=True) if label_rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    cause_eval = pd.DataFrame(cause_eval_rows, columns=["scenario_id", "timestamp", "expected_cause", "candidate_cause", "rank", "top1_correct", "top3_correct", "evaluation_note"])
    return detection, labels, summary, cause_eval


def save_evaluation_plots(summary: pd.DataFrame, cause_eval: pd.DataFrame, output_dir):
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    if summary is not None and not summary.empty:
        pivot = summary.pivot(index="scenario_id", columns="detector", values="f1").fillna(0)
        ax = pivot.plot(kind="bar", figsize=(12, 6)); ax.set_title("Anomaly Detection F1 on Controlled Synthetic Scenarios")
        ax.set_xlabel("Synthetic scenario"); ax.set_ylabel("F1 score"); ax.set_ylim(0, 1.05); ax.grid(axis="y", alpha=.25)
        plt.xticks(rotation=25, ha="right"); plt.tight_layout()
        plt.savefig(output_dir / "scenario_detection_evaluation_plot.png", dpi=160, bbox_inches="tight"); plt.close()
    if cause_eval is not None and not cause_eval.empty:
        scores = cause_eval.groupby("scenario_id")[["top1_correct", "top3_correct"]].mean()
        ax = scores.plot(kind="bar", figsize=(11, 5)); ax.set_title("Root-Cause Ranking Conditional on New Evidence")
        ax.set_xlabel("Synthetic scenario"); ax.set_ylabel("Accuracy fraction"); ax.set_ylim(0, 1.05); ax.grid(axis="y", alpha=.25)
        plt.xticks(rotation=25, ha="right"); plt.tight_layout()
        plt.savefig(output_dir / "scenario_root_cause_evaluation_plot.png", dpi=160, bbox_inches="tight"); plt.close()
