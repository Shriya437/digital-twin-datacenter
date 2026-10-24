
from pprint import pprint

from src.maintenance_manager import prioritize_maintenance_tasks
from src.what_if_simulator import compare_interventions
from src.safety_gate import validate_action
from src.access_control import check_permission
from src.audit_logger import log_action, AUDIT_FILE
from src.model_monitor import evaluate_predictions, check_uncertainty


def main():
    print("\n=== MODULE 7: MAINTENANCE MANAGEMENT ===")

    predictions = [
        {
            "asset_id": "Server-A",
            "risk_score": 0.90,
            "impact_score": 0.80,
            "urgency_score": 0.90,
        },
        {
            "asset_id": "Cooling-Unit-B",
            "risk_score": 0.60,
            "impact_score": 0.70,
            "urgency_score": 0.80,
        },
        {
            "asset_id": "Server-C",
            "risk_score": 0.20,
            "impact_score": 0.30,
            "urgency_score": 0.20,
        },
    ]

    tasks = prioritize_maintenance_tasks(predictions)
    pprint(tasks)

    print("\n=== MODULE 8A: WHAT-IF SIMULATION ===")

    scenarios = compare_interventions(
        baseline_risk=0.80,
        interventions=[
            {
                "name": "Inspection",
                "estimated_risk_reduction": 0.20,
            },
            {
                "name": "Component Replacement",
                "estimated_risk_reduction": 0.50,
            },
        ],
    )
    pprint(scenarios)

    print("\n=== MODULE 8B: SAFETY GATE ===")

    safe = validate_action(
        risk_score=0.20,
        uncertainty=0.10,
        max_risk=0.50,
        max_uncertainty=0.20,
        approved=True,
    )

    blocked = validate_action(
        risk_score=0.90,
        uncertainty=0.10,
        max_risk=0.50,
        max_uncertainty=0.20,
        approved=True,
    )

    print("Low-risk scenario:")
    pprint(safe)

    print("High-risk scenario:")
    pprint(blocked)

    print("\n=== MODULE 9A: ACCESS CONTROL ===")

    print(
        "Viewer can view reports:",
        check_permission("viewer", "view_reports"),
    )

    print(
        "Viewer can manage users:",
        check_permission("viewer", "manage_users"),
    )

    print("\n=== MODULE 9B: AUDIT LOGGING ===")

    log_action(
        user="demo_engineer",
        action="MAINTENANCE_REVIEW",
        details={"asset_id": "Server-A"},
    )

    print("Audit log location:", AUDIT_FILE)
    print("Audit log exists:", AUDIT_FILE.exists())

    if AUDIT_FILE.exists():
        print("Latest audit event:")
        print(
            AUDIT_FILE.read_text(
                encoding="utf-8"
            ).splitlines()[-1]
        )

    print("\n=== MODULE 9C: MODEL MONITORING ===")

    metrics = evaluate_predictions(
        predicted=[0.80, 0.40, 0.20],
        actual=[1.00, 0.00, 0.00],
    )
    print("Prediction metrics:")
    pprint(metrics)

    uncertainty = check_uncertainty(
        uncertainty=0.35,
        allowed_limit=0.20,
    )
    print("Uncertainty check:")
    pprint(uncertainty)

    print("\n=== DEMO COMPLETED ===")


if __name__ == "__main__":
    main()
