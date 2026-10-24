"""Decision support, safety gate enforcement, and action audit logging service."""
import datetime
from typing import Any, Dict, List, Optional

_AUDIT_LOG: List[Dict[str, Any]] = []

MAX_RISK = 0.50
MAX_UNCERTAINTY = 0.25

ALLOWED_ROLES = {"operator", "lead_engineer", "system_admin", "facility_director", "ai_agent"}

def validate_and_log_action(
    action: str,
    target_asset: str,
    operator: str,
    role: str,
    risk_score: float = 0.25,
    uncertainty_score: float = 0.12,
    parameters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Applies safety gate, validates permissions, and logs action."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 1. Role validation
    if role not in ALLOWED_ROLES:
        return {
            "authorized": False,
            "gate_passed": False,
            "rejection_reason": f"Role '{role}' is not authorized to execute data center actions.",
            "timestamp": now_iso
        }

    # 2. Safety Gate evaluation
    reasons = []
    if risk_score > MAX_RISK:
        reasons.append(f"Risk score {risk_score:.2f} exceeds safety threshold {MAX_RISK:.2f}")
    if uncertainty_score > MAX_UNCERTAINTY:
        reasons.append(f"Model uncertainty {uncertainty_score:.2f} exceeds tolerance {MAX_UNCERTAINTY:.2f}")

    gate_passed = len(reasons) == 0

    log_entry = {
        "id": f"AUD-{1000 + len(_AUDIT_LOG) + 1}",
        "timestamp": now_iso,
        "operator": operator,
        "role": role,
        "action": action,
        "target_asset": target_asset,
        "parameters": parameters or {},
        "safety_gate_passed": gate_passed,
        "risk_score": risk_score,
        "uncertainty_score": uncertainty_score,
        "notes": "Action approved by Safety Gate" if gate_passed else f"Blocked by Safety Gate: {'; '.join(reasons)}"
    }

    _AUDIT_LOG.insert(0, log_entry)

    return {
        "authorized": True,
        "gate_passed": gate_passed,
        "rejection_reasons": reasons,
        "audit_entry": log_entry
    }

def get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    return _AUDIT_LOG[:limit]
