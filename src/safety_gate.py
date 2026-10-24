
def validate_action(
    risk_score: float,
    uncertainty: float,
    max_risk: float,
    max_uncertainty: float,
    approved: bool = False,
) -> dict:
    """
    Validate an intervention before it is authorized.

    Lower uncertainty is assumed to be better.
    All scores must be between 0 and 1.
    """
    values = {
        "risk_score": risk_score,
        "uncertainty": uncertainty,
        "max_risk": max_risk,
        "max_uncertainty": max_uncertainty,
    }

    for name, value in values.items():
        if not 0 <= value <= 1:
            raise ValueError(
                f"{name} must be between 0 and 1."
            )

    reasons = []

    if risk_score > max_risk:
        reasons.append("Risk exceeds the allowed limit.")

    if uncertainty > max_uncertainty:
        reasons.append(
            "Prediction uncertainty exceeds the allowed limit."
        )

    if not approved:
        reasons.append(
            "Required human approval has not been recorded."
        )

    return {
        "allowed": len(reasons) == 0,
        "reasons": reasons,
    }
