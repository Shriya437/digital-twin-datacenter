# Digital Twin of Data Centers — Member 2 starter

Implements the initial Member 2 workflow:
- Module 1: logical asset registry and dataset-backed telemetry dependency graph
- Module 4: robust-Z-score and Isolation Forest anomaly detection, plus transparent rule-based root-cause hypotheses

## Project layout

```text
digital-twin-member2/
├── data/
│   ├── m100_node1_digital_twin.csv
│   ├── telemetry_quality_records.csv
│   ├── timestamp_gap_report.csv
│   └── metric_reliability_report.csv   # optional
├── src/
│   ├── __init__.py
│   ├── data_loader.py
│   ├── asset_registry.py
│   ├── dependency_graph.py
│   ├── anomaly_detector.py
│   ├── root_cause.py
│   └── main.py
├── outputs/                            # generated when pipeline runs
├── tests/
├── reference/                          # optional reference reports
├── requirements.txt
└── README.md
```

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m src.main
```

If PowerShell blocks activation, run the venv's interpreter directly:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m src.main
```

Run from the project root (the folder containing `src`, `data`, and `requirements.txt`).

## Input files

The base telemetry CSV is required. `telemetry_quality_records.csv` and `timestamp_gap_report.csv` are optional, but recommended. `metric_reliability_report.csv` is not currently needed by the runtime pipeline; it is retained as reference.

## Generated outputs

- `outputs/asset_registry.csv`
- `outputs/asset_relationships.csv`
- `outputs/asset_graph.json`
- `outputs/anomaly_events.csv`
- `outputs/root_cause_hypotheses.csv`
- `outputs/anomaly_detection_plot.png`
- `outputs/run_summary.json`
- `outputs/timestamp_gap_report_used.csv` (when gap report input is available)

The `outputs/` folder can be empty before the first successful run.

## Interpretation cautions

- An anomaly is not proof of a fault.
- Root-cause ranking scores are heuristic ranks, not probabilities.
- Graph edges represent logical telemetry associations, not verified physical cooling/power topology.
- Sensor units and hardware plausibility limits must be verified from source documentation.
- Isolation Forest imputes missing feature values with per-column medians for model input only; the source CSV is not changed.
- Timestamp gaps are preserved and calculated separately; avoid assuming every adjacent row is exactly 20 seconds apart.
