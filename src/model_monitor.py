
from math import sqrt


def evaluate_predictions(
    predicted: list[float],
    actual: list[float],
) -> dict:
    """
    Compare model predictions against observed outcomes.

    Inputs must be aligned, finite numeric values on
    the same scale. For risk probabilities, use 0–1.
    """
    if not predicted or len(predicted) != len(actual):
        raise ValueError(
            "Predicted and actual lists must have "
            "the same non-zero length."
        )

    pairs = [
        (float(p), float(a))
        for p, a in zip(predicted, actual)
    ]

    if not all(
        0 <= p <= 1 and 0 <= a <= 1
        for p, a in pairs
    ):
        raise ValueError(
            "Predictions and actual outcomes must be in [0, 1]."
        )

    errors = [p - a for p, a in pairs]

    mae = sum(abs(e) for e in errors) / len(errors)
    rmse = sqrt(
        sum(e * e for e in errors) / len(errors)
    )

    return {
        "sample_count": len(pairs),
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
    }


def check_uncertainty(
    uncertainty: float,
    allowed_limit: float,
) -> dict:
    """Check uncertainty against a configured limit."""
    if not 0 <= uncertainty <= 1:
        raise ValueError("Uncertainty must be in [0, 1].")

    if not 0 <= allowed_limit <= 1:
        raise ValueError("Allowed limit must be in [0, 1].")

    return {
        "uncertainty": uncertainty,
        "allowed_limit": allowed_limit,
        "reliable_enough_for_policy": (
            uncertainty <= allowed_limit
        ),
    }
