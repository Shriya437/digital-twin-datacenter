"""Shared, leakage-aware helpers for Member 3 classification experiments."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labeling as L

SEED = 42

def load_task(data_dir: Path, dataset: str = "synthetic"):
    """Return X/y/split for binary anomaly classification.

    dataset='synthetic': injected labels (best for controlled model comparison).
    dataset='observed': heuristic proxy labels; not verified hardware failures.
    """
    if dataset == "observed":
        df = pd.read_csv(data_dir / "m100_node1_labeled_observed.csv")
        df["timestamp_utc"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        seg = L.segment_ids(df["timestamp_utc"])
        labels = pd.to_numeric(df["anomaly_label"], errors="coerce")
        valid = (df["label_valid"] == 1) & labels.notna() & df["split"].isin(["train", "val", "test"])
        y = labels.fillna(0).astype(int)
        split = df["split"].astype(str)
        # only causal features; intentionally exclude rule_* label evidence columns
        X = L.causal_features(df, seg).drop(columns=["segment_id", "pos_in_segment"])
    elif dataset == "synthetic":
        df = pd.read_csv(data_dir / "m100_synthetic_fault_scenarios.csv")
        seg = df["scenario_id"].astype("category").cat.codes
        labels = pd.to_numeric(df["synthetic_label"], errors="coerce")
        split = df["split"].astype(str)
        X = L.causal_features(df, seg).drop(columns=["segment_id", "pos_in_segment"])
        # warmup rows lack sufficient causal context
        valid = labels.notna() & split.isin(["train", "val", "test"])
        valid &= L.causal_features(df, seg)["pos_in_segment"] >= L.WARMUP
        y = labels.fillna(0).astype(int)
    else:
        raise ValueError("dataset must be 'synthetic' or 'observed'")
    X = X.replace([np.inf, -np.inf], np.nan)
    # Retain identical rows and order across models. Imputation is fitted inside each model pipeline.
    X, y, split = X.loc[valid].reset_index(drop=True), y.loc[valid].reset_index(drop=True), split.loc[valid].reset_index(drop=True)
    return X, y, split

def best_f1_threshold(y_true, probabilities):
    y_true = np.asarray(y_true, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    if len(np.unique(y_true)) < 2 or y_true.sum() == 0:
        return 0.5
    precision, recall, thresholds = precision_recall_curve(y_true, p)
    if len(thresholds) == 0:
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.nanargmax(f1))])

def get_splits(split):
    split = pd.Series(split)
    train = np.flatnonzero(split.eq("train").to_numpy())
    val = np.flatnonzero(split.eq("val").to_numpy())
    test = np.flatnonzero(split.eq("test").to_numpy())
    if min(len(train), len(val), len(test)) == 0:
        raise ValueError("One split is empty. Generate labeled datasets first and check split labels.")
    return train, val, test
