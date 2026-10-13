
from typing import Any


def prioritize_maintenance_tasks(
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Rank maintenance tasks using actual prediction inputs.

    Each prediction should contain:
    asset_id, risk_score, impact_score, urgency_score

    The three scores must be on a 0–1 scale.
    """
    tasks = []

    for prediction in predictions:
        required = [
            "asset_id",
            "risk_score",
            "impact_score",
            "urgency_score",
        ]

        missing = [
            key for key in required
            if key not in prediction
        ]

        if missing:
            raise ValueError(
                f"Missing prediction fields: {missing}"
            )

        risk = float(prediction["risk_score"])
        impact = float(prediction["impact_score"])
        urgency = float(prediction["urgency_score"])

        if not all(0 <= x <= 1 for x in [risk, impact, urgency]):
            raise ValueError("Scores must be between 0 and 1.")

        priority = (
            0.50 * risk
            + 0.30 * impact
            + 0.20 * urgency
        )

        task = prediction.copy()
        task["priority_score"] = round(priority, 4)

        if priority >= 0.75:
            task["priority"] = "CRITICAL"
        elif priority >= 0.50:
            task["priority"] = "HIGH"
        elif priority >= 0.25:
            task["priority"] = "MEDIUM"
        else:
            task["priority"] = "LOW"

        tasks.append(task)

    return sorted(
        tasks,
        key=lambda task: task["priority_score"],
        reverse=True,
    )
