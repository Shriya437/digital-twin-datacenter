"""Create stable logical asset IDs and metric mappings from dataset evidence."""
import pandas as pd
from .data_loader import METRICS

METADATA = {
    "ambient": ("temperature_metric", "Ambient temperature telemetry; sensor location not verified"),
    "p0_vdd_temp": ("temperature_metric", "Processor 0 temperature telemetry source"),
    "p1_vdd_temp": ("temperature_metric", "Processor 1 temperature telemetry source"),
    "fan0_0": ("fan_metric", "Fan telemetry metric 0; physical mapping unverified"),
    "fan1_0": ("fan_metric", "Fan telemetry metric 1; physical mapping unverified"),
    "p0_power": ("power_metric", "Processor 0 power telemetry source"),
    "p1_power": ("power_metric", "Processor 1 power telemetry source"),
    "ps0_input_power": ("power_metric", "Power-supply input power telemetry source 0"),
    "ps1_input_power": ("power_metric", "Power-supply input power telemetry source 1"),
    "total_power": ("power_metric", "Dataset-provided total power metric; definition should be verified"),
}


def build_asset_registry(df: pd.DataFrame, quality: pd.DataFrame | None = None) -> pd.DataFrame:
    rows = [{
        "asset_id": "M100_NODE_1", "asset_type": "monitored_node",
        "display_name": "M100 Node 1",
        "description": "Logical monitored node represented by the supplied telemetry dataset",
        "source": "m100_node1_digital_twin.csv", "is_simulated": False,
        "evidence_status": "dataset_backed", "parent_asset_id": "",
    }]
    quality_statuses = {}
    if quality is not None and {"metric_name", "quality_status"}.issubset(quality.columns):
        for metric, group in quality.groupby("metric_name"):
            quality_statuses[metric] = ";".join(sorted(group["quality_status"].dropna().astype(str).unique()))
    for metric in METRICS:
        kind, description = METADATA[metric]
        rows.append({
            "asset_id": f"M100_NODE_1::{metric}", "asset_type": kind,
            "display_name": metric, "description": description,
            "source": "m100_node1_digital_twin.csv", "is_simulated": False,
            "evidence_status": "metric_column_exists_physical_component_unverified",
            "parent_asset_id": "M100_NODE_1",
            "quality_statuses_seen": quality_statuses.get(metric, "not_available"),
            "observed_row_count": int(df[metric].notna().sum()),
            "missing_row_count": int(df[metric].isna().sum()),
        })
    return pd.DataFrame(rows)


def build_metric_asset_mapping() -> pd.DataFrame:
    """Map metric columns to logical telemetry entities, not asserted hardware."""
    return pd.DataFrame([
        {"metric_name": m, "asset_id": f"M100_NODE_1::{m}",
         "mapping_status": "logical_telemetry_entity", "physical_mapping_verified": False}
        for m in METRICS
    ])
