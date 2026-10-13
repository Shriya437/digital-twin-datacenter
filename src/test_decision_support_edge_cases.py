
import json

from src.maintenance_manager import prioritize_maintenance_tasks
from src.what_if_simulator import compare_interventions
from src.safety_gate import validate_action
from src.access_control import check_permission, require_permission
from src.audit_logger import log_action, AUDIT_FILE
from src.model_monitor import evaluate_predictions, check_uncertainty


def expect_error(function, error_type, description):
    try:
        function()
    except error_type:
        print(f"PASS: {description}")
    else:
        raise AssertionError(
            f"FAIL: {description} did not raise {error_type.__name__}"
        )


def test_maintenance_boundaries():
    # Boundary scores and priority thresholds
    predictions = [
        {
            "asset_id": f"Asset-{score}",
            "risk_score": score,
            "impact_score": score,
            "urgency_score": score,
        }
        for score in [0.0, 0.25, 0.50, 0.75, 1.0]
    ]

    tasks = prioritize_maintenance_tasks(predictions)

    assert len(tasks) == 5
    assert tasks[0]["priority_score"] == 1.0
    assert tasks[0]["priority"] == "CRITICAL"

    labels = {
        task["risk_score"]: task["priority"]
        for task in tasks
    }

    assert labels[0.0] == "LOW"
    assert labels[0.25] == "MEDIUM"
    assert labels[0.50] == "HIGH"
    assert labels[0.75] == "CRITICAL"

    expect_error(
        lambda: prioritize_maintenance_tasks([
            {
                "asset_id": "Invalid",
                "risk_score": 1.2,
                "impact_score": 0.5,
                "urgency_score": 0.5,
            }
        ]),
        ValueError,
        "Maintenance rejects out-of-range scores",
    )

    expect_error(
        lambda: prioritize_maintenance_tasks([
            {"asset_id": "Missing", "risk_score": 0.5}
        ]),
        ValueError,
        "Maintenance rejects missing fields",
    )

    print("PASS: Maintenance boundaries and thresholds")


def test_simulation_boundaries():
    results = compare_interventions(
        baseline_risk=1.0,
        interventions=[
            {
                "name": "No change",
                "estimated_risk_reduction": 0.0,
            },
            {
                "name": "Full reduction assumption",
                "estimated_risk_reduction": 1.0,
            },
        ],
    )

    by_name = {
        result["intervention"]: result
        for result in results
    }

    assert by_name["No change"]["estimated_risk"] == 1.0
    assert (
        by_name["Full reduction assumption"]["estimated_risk"]
        == 0.0
    )

    expect_error(
        lambda: compare_interventions(
            0.8,
            [{"name": "Invalid", "estimated_risk_reduction": 1.5}],
        ),
        ValueError,
        "Simulation rejects invalid reduction",
    )

    expect_error(
        lambda: compare_interventions(
            1.1,
            [{"name": "Test", "estimated_risk_reduction": 0.2}],
        ),
        ValueError,
        "Simulation rejects invalid baseline risk",
    )

    expect_error(
        lambda: compare_interventions(
            0.8,
            [{"name": "Missing reduction"}],
        ),
        ValueError,
        "Simulation rejects missing intervention assumptions",
    )

    print("PASS: What-if boundary conditions")


def test_safety_gate():
    # Values exactly at the limits should be accepted
    boundary = validate_action(
        risk_score=0.5,
        uncertainty=0.2,
        max_risk=0.5,
        max_uncertainty=0.2,
        approved=True,
    )

    assert boundary["allowed"] is True

    # Explicitly verify that missing approval blocks an action
    unapproved = validate_action(
        risk_score=0.2,
        uncertainty=0.1,
        max_risk=0.5,
        max_uncertainty=0.2,
        approved=False,
    )

    assert unapproved["allowed"] is False
    assert any(
        "approval" in reason.lower()
        for reason in unapproved["reasons"]
    )

    expect_error(
        lambda: validate_action(
            risk_score=1.5,
            uncertainty=0.1,
            max_risk=0.5,
            max_uncertainty=0.2,
            approved=True,
        ),
        ValueError,
        "Safety gate rejects invalid risk",
    )

    expect_error(
        lambda: validate_action(
            risk_score=0.2,
            uncertainty=-0.1,
            max_risk=0.5,
            max_uncertainty=0.2,
            approved=True,
        ),
        ValueError,
        "Safety gate rejects invalid uncertainty",
    )

    print("PASS: Safety limits and approval checks")


def test_access_control():
    assert check_permission("viewer", "view_reports")
    assert not check_permission("viewer", "manage_users")
    assert not check_permission("unknown", "view_reports")

    expect_error(
        lambda: require_permission("viewer", "manage_users"),
        PermissionError,
        "Access control blocks unauthorized operation",
    )

    print("PASS: Access-control edge cases")


def test_audit_logging():
    action = "EDGE_CASE_TEST"
    log_action(
        user="test_engineer",
        action=action,
        details={"test": True},
    )

    assert AUDIT_FILE.exists()

    lines = AUDIT_FILE.read_text(
        encoding="utf-8"
    ).splitlines()

    event = json.loads(lines[-1])

    assert event["action"] == action
    assert event["user"] == "test_engineer"
    assert event["details"]["test"] is True
    assert "timestamp" in event

    print("PASS: Audit event is written and readable")


def test_model_monitor():
    # Perfect predictions should give zero error
    perfect = evaluate_predictions(
        predicted=[0.0, 1.0],
        actual=[0.0, 1.0],
    )

    assert perfect["mae"] == 0.0
    assert perfect["rmse"] == 0.0

    expect_error(
        lambda: evaluate_predictions([], []),
        ValueError,
        "Monitor rejects empty inputs",
    )

    expect_error(
        lambda: evaluate_predictions([0.2, 0.3], [0.2]),
        ValueError,
        "Monitor rejects mismatched list lengths",
    )

    expect_error(
        lambda: evaluate_predictions([1.2], [1.0]),
        ValueError,
        "Monitor rejects out-of-range predictions",
    )

    assert check_uncertainty(0.2, 0.2)[
        "reliable_enough_for_policy"
    ]

    assert not check_uncertainty(0.21, 0.2)[
        "reliable_enough_for_policy"
    ]

    expect_error(
        lambda: check_uncertainty(1.1, 0.2),
        ValueError,
        "Monitor rejects invalid uncertainty",
    )

    print("PASS: Model-monitoring edge cases")


if __name__ == "__main__":
    tests = [
        test_maintenance_boundaries,
        test_simulation_boundaries,
        test_safety_gate,
        test_access_control,
        test_audit_logging,
        test_model_monitor,
    ]

    for test in tests:
        test()

    print("\nAll Member 4 edge-case tests passed!")
