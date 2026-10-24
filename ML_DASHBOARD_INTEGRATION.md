# ML-to-dashboard integration workflow

## Generate the actual outputs first

From the project root (the folder containing `src/`, `backend/`, and `data/`):

```powershell
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py run_ml_pipeline.py
```

The runner executes the existing project modules in dependency order. It creates outputs under `outputs/`, `outputs/predictive_maintenance_op/`, and `outputs/member3_outputs/`. Run it again whenever the source dataset or ML code changes.

Then start the API and UI in separate terminals:

```powershell
py -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm install
npm run dev
```

## Data integrity rules

- Forecast values and evaluation metrics must come from the prediction/metrics artifacts created by `src.predictive_maintenance` or `src/power_temperature_analytics.py`.
- Anomaly results must come from the Isolation Forest / anomaly-detection output. Empty outputs are returned as empty/unavailable, not replaced by fabricated examples.
- Telemetry cards use records from `data/m100_node1_digital_twin.csv`. Energy totals require generated integration artifacts. PUE remains unavailable unless facility and IT power measurements support it.
- The what-if energy panel is inherently a hypothetical calculation. Its baseline is derived from the dataset's observed mean `total_power`; the result is explicitly labelled as simulated, not an ML prediction. Carbon savings and thermal relief are omitted until verified factors/models are available.
- A valid Remaining Useful Life (RUL) value cannot be claimed from temperature anomaly scores alone. The dashboard returns `null` for RUL until a validated RUL model and target labels are implemented.
- Fault injection is a simulation by design; it must be presented as a scenario, never as an observed real-world event.

If an ML output is missing, the dashboard should show no result / unavailable rather than a made-up score.
