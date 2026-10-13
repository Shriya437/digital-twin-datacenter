
"""Integration demo for Member 4 decision support modules."""

from pathlib import Path
import json

import pandas as pd

from src.maintenance_manager import prioritize_maintenance_tasks
from src.what_if_simulator import compare_interventions
from src.safety_gate import validate_action
from src.access_control import authorize_action
from src.audit_logger import log_action
from src.model_monitor import evaluate_predictions, check_uncertainty


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs"
MEMBER4_OUTPUT = OUTPUT / "member4"
DATA = ROOT / "data"

MAX_ALERT_TIMESTAMPS = 10
MAX_RISK = 0.50
MAX_UNCERTAINTY = 0.20


def assess_telemetry_quality(telemetry):
    """Basic data checks, not a model reliability assessment."""
    if telemetry.empty or "timestamp" not in telemetry.columns:
        return {
            "data_quality_ok": False,
            "reason": "Telemetry is empty or has no timestamp column.",
        }

    metric_columns = [
        column
        for column in telemetry.columns
        if column not in {
            "timestamp",
            "gap_seconds",
            "telemetry_gap",
            "has_missing_metric",
        }
    ]

    valid_timestamps = pd.to_datetime(
        telemetry["timestamp"], utc=True, errors="coerce"
    ).notna()

    if metric_columns:
        missing_rows = telemetry[metric_columns].isna().any(axis=1)
        missing_row_fraction = float(missing_rows.mean())
    else:
        missing_row_fraction = 1.0

    valid_timestamp_fraction = float(valid_timestamps.mean())

    # Explicit demo thresholds; these are not domain-certified limits.
    quality_ok = (
        valid_timestamp_fraction >= 0.99
        and missing_row_fraction <= 0.05
        and bool(metric_columns)
    )

    return {
        "data_quality_ok": quality_ok,
        "row_count": int(len(telemetry)),
        "metric_column_count": len(metric_columns),
        "valid_timestamp_fraction": round(valid_timestamp_fraction, 4),
        "rows_with_missing_metrics_fraction": round(
            missing_row_fraction, 4
        ),
        "thresholds": {
            "minimum_valid_timestamp_fraction": 0.99,
            "maximum_rows_with_missing_metrics_fraction": 0.05,
        },
        "note": "Basic demo checks only; thresholds require domain review.",
    }


def main():
    events_path = OUTPUT / "anomaly_events.csv"
    causes_path = OUTPUT / "root_cause_hypotheses.csv"
    telemetry_path = DATA / "m100_node1_digital_twin.csv"

    for path in (events_path, causes_path, telemetry_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: {path}\n"
                "Run 'python -m src.main' first."
            )

    MEMBER4_OUTPUT.mkdir(parents=True, exist_ok=True)

    events = pd.read_csv(events_path)
    causes = pd.read_csv(causes_path)
    telemetry = pd.read_csv(telemetry_path)

    required_event_columns = {"timestamp", "anomaly_score"}
    required_cause_columns = {
        "timestamp", "candidate_cause", "rank", "evidence"
    }

    if not required_event_columns.issubset(events.columns):
        raise ValueError(
            f"Anomaly file must contain {sorted(required_event_columns)}"
        )

    if not required_cause_columns.issubset(causes.columns):
        raise ValueError(
            f"Root-cause file must contain {sorted(required_cause_columns)}"
        )

    quality = assess_telemetry_quality(telemetry)

    # Choose the highest-ranked cause for each timestamp.
    causes["rank"] = pd.to_numeric(causes["rank"], errors="coerce")
    top_causes = (
        causes.sort_values("rank")
        .drop_duplicates("timestamp", keep="first")
    )
    cause_lookup = {
        str(row["timestamp"]): row
        for _, row in top_causes.iterrows()
    }

    # Keep one strongest anomaly per timestamp for this demo.
    events["anomaly_score"] = pd.to_numeric(
        events["anomaly_score"], errors="coerce"
    )
    events = events.dropna(subset=["timestamp", "anomaly_score"])
    events = events.sort_values("anomaly_score", ascending=False)
    events = events.drop_duplicates("timestamp", keep="first")
    events = events.head(MAX_ALERT_TIMESTAMPS)

    task_inputs = []
    task_context = []
    scenarios = []
    safety_results = []
    monitoring_results = []

    for _, event in events.iterrows():
        timestamp = str(event["timestamp"])
        metric = str(event.get("metric_name", "unknown"))
        anomaly_score = float(event["anomaly_score"])

        # Anomaly score is used as a bounded prioritization input here,
        # not as a calibrated probability of equipment failure.
        risk_score = min(1.0, max(0.0, anomaly_score))

        cause = cause_lookup.get(timestamp)
        if cause is None:
            suspected_cause = "unknown_or_insufficient_evidence"
            evidence = "No ranked root-cause hypothesis for this timestamp."
        else:
            suspected_cause = str(cause["candidate_cause"])
            evidence = str(cause["evidence"])

        evidence_sufficient = (
            cause is not None
            and str(cause.get("evidence_status", "")).lower()
            == "preliminary_rule_evidence"
        )

        asset_id = (
            f"M100_NODE_1::{metric}"
            if metric not in {"unknown", "MULTIVARIATE", "nan"}
            else "M100_NODE_1"
        )

        # Transparent demo heuristics, not validated impact or urgency models.
        impact_score = 0.50 if metric == "MULTIVARIATE" else 0.40
        urgency_score = risk_score

        task_inputs.append({
            "asset_id": asset_id,
            "risk_score": risk_score,
            "impact_score": impact_score,
            "urgency_score": urgency_score,
            "alert_timestamp": timestamp,
            "metric_name": metric,
            "suspected_cause": suspected_cause,
            "evidence": evidence,
        })

        task_context.append({
            "timestamp": timestamp,
            "asset_id": asset_id,
            "metric_name": metric,
            "anomaly_score": anomaly_score,
            "suspected_cause": suspected_cause,
            "evidence": evidence,
        })

        # Explicitly assumed reductions for scenario comparison only.
        interventions = [
            {
                "name": "Inspect affected component",
                "estimated_risk_reduction": 0.20,
            },
            {
                "name": "Replace component if inspection confirms fault",
                "estimated_risk_reduction": 0.50,
            },
        ]

        comparison = compare_interventions(
            baseline_risk=risk_score,
            interventions=interventions,
        )

        scenarios.append({
            "timestamp": timestamp,
            "baseline_risk_assumption": risk_score,
            "note": (
                "Illustrative reductions, not validated intervention "
                "effects or calibrated risk predictions."
            ),
            "alternatives": comparison,
        })

        # The repository does not supply a validated uncertainty estimate
        # for these alerts. Use the maximum uncertainty as a fail-closed
        # sentinel; it must not be interpreted as measured uncertainty.
        uncertainty_for_gate = 1.0
        approved = False

        safety = validate_action(
            risk_score=risk_score,
            uncertainty=uncertainty_for_gate,
            max_risk=MAX_RISK,
            max_uncertainty=MAX_UNCERTAINTY,
            approved=approved,
        )

        safety_results.append({
            "timestamp": timestamp,
            "proposed_action": comparison[0]["intervention"],
            "allowed": safety["allowed"],
            "reasons": safety["reasons"],
            "uncertainty_estimate_available": False,
            "human_approval_recorded": approved,
        })

        # Exercise access control for the simulated workflow.
        authorize_action(
            user="demo_operator",
            role="maintenance_engineer",
            action="run_simulation",
            details={"timestamp": timestamp},
        )

        authorize_action(
            user="demo_operator",
            role="maintenance_engineer",
            action="create_maintenance_task",
            details={"asset_id": asset_id, "timestamp": timestamp},
        )

        log_action(
            user="demo_operator",
            action="RECOMMENDATION_EVALUATED",
            details={
                "timestamp": timestamp,
                "asset_id": asset_id,
                "safety_result": safety,
                "evidence": evidence,
                "model_version": "prototype-v1",
                "decision_status": "PENDING_HUMAN_REVIEW",
            },
            outcome="SUCCESS",
        )

    ranked_tasks = prioritize_maintenance_tasks(task_inputs)

    # Attach the original context fields to the ranked tasks.
    context_lookup = {
        (item["asset_id"], item["alert_timestamp"]): item
        for item in task_inputs
    }
    for task in ranked_tasks:
        context = context_lookup.get(
            (task["asset_id"], task["alert_timestamp"]), {}
        )
        task.update({
            "metric_name": context.get("metric_name", "unknown"),
            "suspected_cause": context.get("suspected_cause", "unknown"),
            "evidence": context.get("evidence", ""),
        })

    # The repo currently has no verified actual failure outcomes to pair
    # with these alert scores, so don't calculate MAE/RMSE as if it did.
    uncertainty_check = check_uncertainty(
    uncertainty=1.0,
    allowed_limit=MAX_UNCERTAINTY,
)

    monitoring_results.append({
        "prediction_metrics_status": "NOT_EVALUATED",
        "reason": (
            "No aligned, validated predicted-versus-actual failure outcomes "
            "are available."
        ),
        "uncertainty_check": uncertainty_check,
        "uncertainty_is_measured": False,
    })

    with (MEMBER4_OUTPUT / "maintenance_tasks.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        pd.DataFrame(ranked_tasks).to_csv(file, index=False)

    output_files = {
        "scenario_comparisons.json": scenarios,
        "safety_decisions.json": safety_results,
        "data_quality.json": quality,
        "model_monitoring.json": monitoring_results,
        "alert_context.json": task_context,
    }

    for filename, content in output_files.items():
        with (MEMBER4_OUTPUT / filename).open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(content, file, indent=2, default=str)

    print("\nMember 4 integration demo completed.")
    print(f"Alerts processed: {len(task_context)}")
    print(f"Maintenance tasks prioritized: {len(ranked_tasks)}")
    print(f"Data quality acceptable under demo thresholds: {quality['data_quality_ok']}")
    print(f"Recommendations blocked pending evidence/approval: {sum(not x['allowed'] for x in safety_results)}")
    print(f"Outputs saved to: {MEMBER4_OUTPUT}")
    print("No equipment actions were executed.")
    print("Scenario reductions are assumptions, not validated predictions.")


if __name__ == "__main__":
    main()
