# -*- coding: utf-8 -*-
"""Download archive, extract selective metric Parquets, and generate node 1 CSV."""

import os
import shutil
import tarfile
import requests
import pandas as pd
from functools import reduce
from config import (
    DATA_DIR,
    TAR_URL,
    TAR_PATH,
    SELECTED_METRICS_DIR,
    SELECTED_METRICS,
    METRICS,
    NODE_ID,
    DATA_PATH
)

def check_disk_space():
    total, used, free = shutil.disk_usage(str(DATA_DIR))
    print("Free runtime space (GB):", round(free / 1e9, 2))

def download_dataset():
    if TAR_PATH.exists():
        print(f"Archive already exists at {TAR_PATH}, skipping download.")
        return

    print(f"Downloading dataset from {TAR_URL}...")
    with requests.get(TAR_URL, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(TAR_PATH, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    print("Download complete!")

def inspect_archive():
    with tarfile.open(TAR_PATH, "r:") as tar:
        members = tar.getmembers()
        print("Total files:", len(members))
        print("\nFirst 30 archive entries:")
        for member in members[:30]:
            print(member.name, "|", round(member.size / 1024, 2), "KB")

        metrics = sorted({
            member.name.split("/metric=")[1].split("/")[0]
            for member in members
            if "/metric=" in member.name and member.isfile()
        })

    print("Total metric files:", len(metrics))
    for metric in metrics:
        print(metric)

def extract_selected_metrics():
    with tarfile.open(TAR_PATH, "r:") as tar:
        extracted = []
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".parquet"):
                continue
            if "/metric=" not in member.name:
                continue

            metric = member.name.split("/metric=")[1].split("/")[0]
            if metric in SELECTED_METRICS:
                source = tar.extractfile(member)
                if source is not None:
                    destination = SELECTED_METRICS_DIR / f"{metric}.parquet"
                    with source, open(destination, "wb") as f:
                        f.write(source.read())
                    extracted.append(metric)

    print("Extracted metrics:", len(extracted))
    print("Files:", sorted(extracted))

def inspect_extracted_metrics():
    for filename in sorted(os.listdir(SELECTED_METRICS_DIR)):
        if not filename.endswith(".parquet"):
            continue
        path = SELECTED_METRICS_DIR / filename
        df = pd.read_parquet(path)
        print("\nMetric:", filename.removesuffix(".parquet"))
        print("Columns:", df.columns.tolist())
        print("Shape:", df.shape)
        print(df.head(3).to_string(index=False))

def validate_metric_nodes():
    metric_files = sorted(
        f for f in os.listdir(SELECTED_METRICS_DIR)
        if f.endswith(".parquet")
    )
    node_sets = {}
    summary = []

    for filename in metric_files:
        metric = filename.removesuffix(".parquet")
        path = SELECTED_METRICS_DIR / filename

        df = pd.read_parquet(path, columns=["timestamp", "value", "node"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        node_sets[metric] = set(df["node"].dropna().unique())

        summary.append({
            "metric": metric,
            "rows": len(df),
            "unique_nodes": df["node"].nunique(),
            "missing_values": int(df["value"].isna().sum()),
            "start_time": str(df["timestamp"].min()),
            "end_time": str(df["timestamp"].max()),
            "min_value": df["value"].min(),
            "median_value": df["value"].median(),
            "max_value": df["value"].max()
        })
        del df

    summary_df = pd.DataFrame(summary)
    print("METRIC VALIDATION SUMMARY")
    print(summary_df.to_string())

    print("\nNODE OVERLAP BETWEEN METRICS")
    for metric, nodes in node_sets.items():
        print(f"{metric}: {len(nodes)} unique nodes")

    common_nodes = set.intersection(*node_sets.values())
    print("\nNodes common to ALL selected metrics:", len(common_nodes))
    print("Sample common nodes:", list(sorted(common_nodes))[:20])

def build_node1_digital_twin_csv():
    frames = []
    for metric in METRICS:
        path = SELECTED_METRICS_DIR / f"{metric}.parquet"
        df = pd.read_parquet(path, columns=["timestamp", "value", "node"])
        df["node"] = df["node"].astype(str)
        df = df[df["node"] == NODE_ID].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df[["timestamp", "value"]].rename(columns={"value": metric})

        if df["timestamp"].duplicated().any():
            raise ValueError(f"Duplicate timestamps in {metric}")

        frames.append(df)
        del df

    combined = reduce(
        lambda left, right: pd.merge(left, right, on="timestamp", how="outer"),
        frames
    )
    combined = combined.sort_values("timestamp").reset_index(drop=True)

    combined["gap_seconds"] = (
        combined["timestamp"].diff().dt.total_seconds()
    )
    combined["telemetry_gap"] = (
        combined["gap_seconds"] > 60
    ).fillna(False)

    combined["has_missing_metric"] = (
        combined[METRICS].isna().any(axis=1)
    )

    combined.to_csv(DATA_PATH, index=False)
    print("Dataset created:", DATA_PATH)
    print("Rows:", len(combined))
    print("Columns:", len(combined.columns))
    print("Missing readings by metric:")
    print(combined[METRICS].isna().sum())
    print("Telemetry gaps:", int(combined["telemetry_gap"].sum()))
    print("Largest gap (seconds):", combined["gap_seconds"].max())
    print("\nPreview:")
    print(combined.head().to_string(index=False))
    print("\nFile size (MB):", round(os.path.getsize(DATA_PATH) / 1e6, 2))

def run_preparation_pipeline():
    check_disk_space()
    download_dataset()
    inspect_archive()
    extract_selected_metrics()
    inspect_extracted_metrics()
    validate_metric_nodes()
    build_node1_digital_twin_csv()

if __name__ == "__main__":
    run_preparation_pipeline()