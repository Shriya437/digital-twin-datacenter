
def compare_interventions(
    baseline_risk: float,
    interventions: list[dict],
) -> list[dict]:
    """
    Compare intervention scenarios using explicitly
    supplied estimated effects.

    Each intervention requires:
    name, estimated_risk_reduction

    Risk reduction is an assumption supplied by the
    user or an independently validated model.
    """
    if not 0 <= baseline_risk <= 1:
        raise ValueError("Baseline risk must be between 0 and 1.")

    results = []

    for intervention in interventions:
        if "name" not in intervention:
            raise ValueError("Intervention name is required.")

        if "estimated_risk_reduction" not in intervention:
            raise ValueError(
                "An explicit estimated risk reduction is required."
            )

        reduction = float(
            intervention["estimated_risk_reduction"]
        )

        if not 0 <= reduction <= 1:
            raise ValueError(
                "Risk reduction must be between 0 and 1."
            )

        estimated_risk = max(
            0.0,
            baseline_risk * (1 - reduction),
        )

        results.append({
            "intervention": intervention["name"],
            "baseline_risk": baseline_risk,
            "estimated_risk": round(estimated_risk, 4),
            "estimated_reduction": round(
                baseline_risk - estimated_risk, 4
            ),
            "status": "ESTIMATE_ONLY",
        })

    return sorted(
        results,
        key=lambda item: item["estimated_risk"],
    )
