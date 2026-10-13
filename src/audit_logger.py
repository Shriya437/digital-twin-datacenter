
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_FILE = (
    Path(__file__).resolve().parent.parent
    / "outputs"
    / "audit_log.jsonl"
)


def log_action(
    user: str,
    action: str,
    details: dict[str, Any] | None = None,
    outcome: str = "SUCCESS",
) -> None:
    """Append a validated audit event to the log."""

    if not isinstance(user, str) or not user.strip():
        raise ValueError("User must be a non-empty string.")

    if not isinstance(action, str) or not action.strip():
        raise ValueError("Action must be a non-empty string.")

    if outcome not in {"SUCCESS", "DENIED", "FAILURE"}:
        raise ValueError(
            "Outcome must be SUCCESS, DENIED, or FAILURE."
        )

    if details is not None and not isinstance(details, dict):
        raise ValueError("Details must be a dictionary or None.")

    AUDIT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    event = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "user": user,
        "action": action,
        "details": details or {},
        "outcome": outcome,
    }

    with AUDIT_FILE.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, default=str) + "\n")
