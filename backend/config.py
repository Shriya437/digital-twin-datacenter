"""Backend configuration and file paths."""
from pathlib import Path

# Root directory of the repository
ROOT_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT_DIR / "data"
OUTPUTS_DIR = ROOT_DIR / "outputs"
FAULT_PROP_DIR = OUTPUTS_DIR / "fault_propagation"
MEMBER3_DIR = OUTPUTS_DIR / "member3_outputs"
PRED_MAINT_DIR = OUTPUTS_DIR / "predictive_maintenance_op"
SCENARIOS_DIR = OUTPUTS_DIR / "scenarios"

# Key data files
TELEMETRY_CSV = DATA_DIR / "m100_node1_digital_twin.csv"
METRIC_RELIABILITY_CSV = DATA_DIR / "metric_reliability_report.csv"
QUALITY_RECORDS_CSV = DATA_DIR / "telemetry_quality_records.csv"
GAP_REPORT_CSV = DATA_DIR / "timestamp_gap_report.csv"

# Key output files
ASSET_REGISTRY_CSV = OUTPUTS_DIR / "asset_registry.csv"
ASSET_RELATIONSHIPS_CSV = OUTPUTS_DIR / "asset_relationships.csv"
ASSET_GRAPH_JSON = OUTPUTS_DIR / "asset_graph.json"
ANOMALY_EVENTS_CSV = OUTPUTS_DIR / "anomaly_events.csv"
ROOT_CAUSE_CSV = OUTPUTS_DIR / "root_cause_hypotheses.csv"
POTENTIAL_IMPACT_CSV = OUTPUTS_DIR / "potential_impact_report.csv"
TELEMETRY_FEATURES_CSV = OUTPUTS_DIR / "telemetry_features.csv"
GAP_REPORT_USED_CSV = OUTPUTS_DIR / "timestamp_gap_report_used.csv"

# Fault propagation outputs
FAULT_IMPACT_JSON = FAULT_PROP_DIR / "fault_impact_report.json"
FAULT_IMPACT_CSV = FAULT_PROP_DIR / "fault_impact_report.csv"
FAULT_SCENARIOS_CSV = FAULT_PROP_DIR / "fault_propagation_scenarios.csv"
INTEGRATED_FAULT_JSON = FAULT_PROP_DIR / "integrated_fault_workflow.json"
SCENARIO_IMPACT_MATRIX_JSON = FAULT_PROP_DIR / "scenario_impact_matrix.json"
ENERGY_ANALYSIS_CSV = FAULT_PROP_DIR / "energy_analysis.csv"

# Multiclass predictions and labeling outputs
MULTICLASS_PRED_CSV = OUTPUTS_DIR / "multiclass_predictions.csv"
MULTICLASS_MODEL_JOBLIB = OUTPUTS_DIR / "multiclass_fault_classifier.joblib"

# Predictive maintenance outputs
PRED_WARNINGS_CSV = PRED_MAINT_DIR / "future_temperature_warnings.csv"
EARLY_WARNINGS_CSV = PRED_MAINT_DIR / "temperature_early_warnings.csv"
DEGRADATION_CSV = PRED_MAINT_DIR / "degradation_indicators.csv"
FORECAST_METRICS_CSV = PRED_MAINT_DIR / "forecast_metrics.csv"
STANDARDIZED_PRED_CSV = PRED_MAINT_DIR / "standardized_predictions.csv"
ANOMALY_RESULTS_CSV = PRED_MAINT_DIR / "anomaly_detection_results.csv"
ALL_MODEL_EVALUATION_CSV = PRED_MAINT_DIR / "all_model_evaluation_metrics.csv"

# Member 3 outputs
ENERGY_SUMMARY_CSV = MEMBER3_DIR / "energy_integration_summary.csv"
CORRELATIONS_CSV = MEMBER3_DIR / "metric_correlations.csv"
CORRELATION_INTERPRETATION_CSV = MEMBER3_DIR / "correlation_interpretation.csv"
PUE_CSV = MEMBER3_DIR / "pue_requirements.csv"
WHAT_IF_CSV = MEMBER3_DIR / "what_if_power_comparison.csv"
TEMP_DIFFERENCE_CSV = MEMBER3_DIR / "processor_temperature_difference.csv"

# Thresholds
LATE_THRESHOLD_SECONDS = 60
STALE_THRESHOLD_SECONDS = 120
