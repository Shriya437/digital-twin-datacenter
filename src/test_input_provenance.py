
from src.input_provenance import validate_input_record


def test_model_prediction():
    result = validate_input_record(
        {
            "value": 0.82,
            "source_type": "model_prediction",
            "source_name": "datacenter_risk_model",
            "model_version": "1.0",
            "timestamp": "2026-10-13T17:00:00+00:00",
        },
        "risk_score",
    )

    assert result["value"] == 0.82
    assert result["validation_status"] == "metadata_validated"

    print("PASS: Model prediction metadata")


def test_simulation_assumption():
    result = validate_input_record(
        {
            "value": 0.25,
            "source_type": "simulation_assumption",
            "source_name": "demo_configuration",
            "assumption_note": (
                "Illustrative 25% intervention risk reduction"
            ),
        },
        "intervention_effect",
    )

    assert result["value"] == 0.25

    print("PASS: Simulation assumption is identified")


def test_missing_model_version():
    try:
        validate_input_record(
            {
                "value": 0.82,
                "source_type": "model_prediction",
                "source_name": "datacenter_risk_model",
                "timestamp": "2026-10-13T17:00:00+00:00",
            },
            "risk_score",
        )
    except ValueError:
        print("PASS: Missing model version rejected")
    else:
        raise AssertionError("Missing model version was accepted")


def test_invalid_timestamp():
    try:
        validate_input_record(
            {
                "value": 0.82,
                "source_type": "measured_data",
                "source_name": "sensor_01",
                "timestamp": "not-a-date",
            },
            "risk_score",
        )
    except ValueError:
        print("PASS: Invalid timestamp rejected")
    else:
        raise AssertionError("Invalid timestamp was accepted")


def test_missing_assumption_note():
    try:
        validate_input_record(
            {
                "value": 0.25,
                "source_type": "simulation_assumption",
                "source_name": "demo_configuration",
            },
            "intervention_effect",
        )
    except ValueError:
        print("PASS: Missing assumption note rejected")
    else:
        raise AssertionError("Missing assumption note was accepted")


if __name__ == "__main__":
    test_model_prediction()
    test_simulation_assumption()
    test_missing_model_version()
    test_invalid_timestamp()
    test_missing_assumption_note()

    print("\nAll input provenance tests passed!")
