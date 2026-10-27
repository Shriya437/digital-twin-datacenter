"""Generate the data/ML artifacts consumed by the FastAPI dashboard.

Run from the repository root: python run_ml_pipeline.py
This may take several minutes because models are trained and reports/plots are generated.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ([sys.executable, "-m", "src.main"], "Core data, anomaly detection, root-cause and graph pipeline"),
    ([sys.executable, "-m", "src.predictive_maintenance"], "Forecasting, Isolation Forest, degradation and warnings"),
    ([sys.executable, "src/power_temperature_analytics.py", "--output-dir", "outputs/member3_outputs"], "Energy integration, correlations and temperature forecasting"),
    ([sys.executable, "data/m100_labeling/ml_labeling/train_baselines.py", "--data-dir", "data/m100_labeling/outputs/labeled_dataset"], "Multiclass fault classification & row-level prediction sync"),
    ([sys.executable, "src/fault_propogation.py"], "Graph-based fault impact analysis & scenario connection"),
]

for command, label in STEPS:
    print(f"\n{'=' * 78}\n{label}\n{'=' * 78}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)

print("\nAll pipelines completed. You can now start the backend and frontend.")
