
from datetime import datetime


SOURCE_TYPES = {
    "model_prediction",
    "measured_data",
    "human_estimate",
    "simulation_assumption",
}


def validate_input_record(
    record: dict,
    field_name: str,
) -> dict:
    """
    Validate a risk, uncertainty, or intervention-effect input
    and require metadata describing where it came from.

    This validates the supplied metadata; it does not independently
    prove that the claimed source is authentic.
    """
    required = ["value", "source_type", "source_name"]

    missing = [
        field for field in required
        if field not in record
    ]

    if missing:
        raise ValueError(
            f"{field_name}: missing fields {missing}"
        )

    source_type = record["source_type"]

    if source_type not in SOURCE_TYPES:
        raise ValueError(
            f"{field_name}: invalid source_type '{source_type}'"
        )

    try:
        value = float(record["value"])
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name}: value must be numeric"
        )

    if not 0 <= value <= 1:
        raise ValueError(
            f"{field_name}: value must be between 0 and 1"
        )

    if not isinstance(record["source_name"], str) or not record[
        "source_name"
    ].strip():
        raise ValueError(
            f"{field_name}: source_name cannot be empty"
        )

    if source_type == "model_prediction":
        if not record.get("model_version"):
            raise ValueError(
                f"{field_name}: model_version is required "
                "for model predictions"
            )

    if source_type in {
        "model_prediction",
        "measured_data",
        "human_estimate",
    }:
        timestamp = record.get("timestamp")

        if not timestamp:
            raise ValueError(
                f"{field_name}: timestamp is required "
                f"for {source_type}"
            )

        try:
            datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            raise ValueError(
                f"{field_name}: timestamp must be ISO 8601"
            )

    if source_type == "simulation_assumption":
        if not record.get("assumption_note"):
            raise ValueError(
                f"{field_name}: assumption_note is required "
                "for simulation assumptions"
            )

    result = record.copy()
    result["value"] = value
    result["field_name"] = field_name
    result["validation_status"] = "metadata_validated"

    return result
