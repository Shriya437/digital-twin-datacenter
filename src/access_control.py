
from src.audit_logger import log_action


ROLE_PERMISSIONS = {
    "viewer": {
        "view_predictions",
        "view_reports",
    },
    "analyst": {
        "view_predictions",
        "view_reports",
        "run_simulation",
    },
    "maintenance_engineer": {
        "view_predictions",
        "view_reports",
        "run_simulation",
        "create_maintenance_task",
    },
    "admin": {
        "view_predictions",
        "view_reports",
        "run_simulation",
        "create_maintenance_task",
        "manage_users",
        "view_audit_logs",
    },
}


def check_permission(role: str, action: str) -> bool:
    """Return whether the configured role permits an action."""
    if role not in ROLE_PERMISSIONS:
        return False

    return action in ROLE_PERMISSIONS[role]


def require_permission(role: str, action: str) -> None:
    """Raise an exception if the role lacks permission."""
    if not check_permission(role, action):
        raise PermissionError(
            f"Role '{role}' cannot perform '{action}'."
        )


def authorize_action(
    user: str,
    role: str,
    action: str,
    details: dict | None = None,
) -> dict:
    """
    Authorize an operation and audit the decision.

    Call this at the operation's execution boundary,
    before carrying out the protected operation.
    """
    allowed = check_permission(role, action)

    event_details = {
        "role": role,
        **(details or {}),
    }

    log_action(
        user=user,
        action=action,
        details=event_details,
        outcome="SUCCESS" if allowed else "DENIED",
    )

    if not allowed:
        raise PermissionError(
            f"Access denied: role '{role}' cannot "
            f"perform '{action}'."
        )

    return {
        "allowed": True,
        "user": user,
        "role": role,
        "action": action,
    }
