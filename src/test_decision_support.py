
from src.maintenance_manager import prioritize_maintenance_tasks
from src.what_if_simulator import compare_interventions
from src.safety_gate import validate_action
from src.access_control import check_permission, require_permission
from src.audit_logger import log_action, AUDIT_FILE
from src.model_monitor import evaluate_predictions, check_uncertainty

def test_maintenance_manager():
    predictions = [
        {
            "asset_id": "Server-A",
            "risk_score": 0.90,
            "impact_score": 0.80,
            "urgency_score": 0.90,
        },
        {
            "asset_id": "Server-B",
            "risk_score": 0.30,
            "impact_score": 0.40,
            "urgency_score": 0.20,
        },
    ]

    tasks = prioritize_maintenance_tasks(predictions)

    assert len(tasks) == 2
    assert tasks[0]["asset_id"] == "Server-A"
    assert tasks[0]["priority"] == "CRITICAL"

    print("PASS: Maintenance prioritization")


def test_what_if_simulator():
    results = compare_interventions(
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

    assert len(results) == 2
    assert results[0]["intervention"] == "Component Replacement"
    assert results[0]["estimated_risk"] == 0.40

    print("PASS: What-if simulation")


def test_safety_gate():
    result = validate_action(
        risk_score=0.20,
        uncertainty=0.10,
        max_risk=0.50,
        max_uncertainty=0.20,
        approved=True,
    )

    assert result["allowed"] is True

    blocked = validate_action(
        risk_score=0.90,
        uncertainty=0.10,
        max_risk=0.50,
        max_uncertainty=0.20,
        approved=True,
    )

    assert blocked["allowed"] is False

    print("PASS: Safety gate")


def test_access_control():
    assert check_permission("viewer", "view_reports")
    assert not check_permission("viewer", "manage_users")
    assert not check_permission("unknown", "view_reports")

    try:
        require_permission("viewer", "manage_users")
    except PermissionError:
        pass
    else:
        raise AssertionError("Unauthorized action was not blocked")

    print("PASS: Access control")


def test_audit_logger():
    log_action(
        user="test_engineer",
        action="TEST_MAINTENANCE_REVIEW",
        details={"asset_id": "Server-A"},
    )

    assert AUDIT_FILE.exists()

    last_line = AUDIT_FILE.read_text(
        encoding="utf-8"
    ).strip().splitlines()[-1]

    assert "TEST_MAINTENANCE_REVIEW" in last_line

    print("PASS: Audit logging")


def test_model_monitor():
    metrics = evaluate_predictions(
        predicted=[0.80, 0.40, 0.20],
        actual=[1.00, 0.00, 0.00],
    )

    assert metrics["sample_count"] == 3
    assert metrics["mae"] > 0
    assert metrics["rmse"] > 0

    result = check_uncertainty(
        uncertainty=0.10,
        allowed_limit=0.20,
    )

    assert result["reliable_enough_for_policy"] is True

    print("PASS: Model monitoring")


if __name__ == "__main__":
    tests = [
        test_maintenance_manager,
        test_what_if_simulator,
        test_safety_gate,
        test_access_control,
        test_audit_logger,
        test_model_monitor,
    ]

    for test in tests:
        test()

    print("\nAll six Member 4 module tests passed!")
