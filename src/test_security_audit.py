
import json

from src.access_control import authorize_action
from src.audit_logger import AUDIT_FILE


def read_latest_events(count=2):
    lines = AUDIT_FILE.read_text(
        encoding="utf-8"
    ).splitlines()

    return [
        json.loads(line)
        for line in lines[-count:]
    ]


def test_allowed_action_is_logged():
    result = authorize_action(
        user="test_analyst",
        role="analyst",
        action="run_simulation",
        details={"test_case": "allowed"},
    )

    assert result["allowed"] is True

    event = read_latest_events(1)[0]

    assert event["user"] == "test_analyst"
    assert event["action"] == "run_simulation"
    assert event["outcome"] == "SUCCESS"

    print("PASS: Authorized operation is logged")


def test_denied_action_is_logged():
    try:
        authorize_action(
            user="test_viewer",
            role="viewer",
            action="manage_users",
            details={"test_case": "denied"},
        )
    except PermissionError:
        pass
    else:
        raise AssertionError(
            "Unauthorized operation was not blocked"
        )

    event = read_latest_events(1)[0]

    assert event["user"] == "test_viewer"
    assert event["action"] == "manage_users"
    assert event["outcome"] == "DENIED"

    print("PASS: Denied operation is logged")


def test_unknown_role_is_denied():
    try:
        authorize_action(
            user="unknown_user",
            role="unknown_role",
            action="view_reports",
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Unknown role was accepted")

    event = read_latest_events(1)[0]

    assert event["outcome"] == "DENIED"

    print("PASS: Unknown role is denied and logged")


if __name__ == "__main__":
    test_allowed_action_is_logged()
    test_denied_action_is_logged()
    test_unknown_role_is_denied()

    print("\nAll security and audit tests passed!")
