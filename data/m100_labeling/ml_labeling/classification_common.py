"""Shared, leakage-aware helpers for Member 3 classification experiments."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, precision_recall_fscore_support, accuracy_score, classification_report, confusion_matrix

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labeling as L

SEED = 42

def resolve_data_dir(data_dir: Path | str) -> Path:
    p = Path(data_dir)
    if p.exists():
        return p
    candidates = [
        HERE.parent / "outputs" / "labeled_dataset",
        HERE.parent.parent.parent / "data" / "m100_labeling" / "outputs" / "labeled_dataset",
    ]
    for c in candidates:
        if c.exists():
            return c
    return p

def load_task(data_dir: Path, dataset: str = "synthetic", task: str = "multiclass"):
    """Return X/y/split for anomaly classification.

    task='multiclass': predict specific fault types (normal, thermal_anomaly, etc.).
    task='binary': predict binary anomaly (0=normal, 1=anomaly).

    dataset='synthetic': injected labels (best for controlled model comparison).
    dataset='observed': heuristic proxy labels; not verified hardware failures.
    """
    data_dir = resolve_data_dir(data_dir)
    if dataset == "observed":
        df = pd.read_csv(data_dir / "m100_node1_labeled_observed.csv")
        df["timestamp_utc"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        seg = L.segment_ids(df["timestamp_utc"])
        split = df["split"].astype(str)
        if task == "multiclass":
            labels = df["fault_type"]
            valid = (df["label_valid"] == 1) & labels.notna() & (~labels.isin(["ambiguous_unknown", "insufficient_context"])) & split.isin(["train", "val", "test"])
            y = labels.astype(str)
        elif task == "binary":
            labels = pd.to_numeric(df["anomaly_label"], errors="coerce")
            valid = (df["label_valid"] == 1) & labels.notna() & split.isin(["train", "val", "test"])
            y = labels.fillna(0).astype(int)
        else:
            raise ValueError("task must be 'multiclass' or 'binary'")
        # only causal features; intentionally exclude rule_* label evidence columns
        X = L.causal_features(df, seg).drop(columns=["segment_id", "pos_in_segment"])
    elif dataset == "synthetic":
        df = pd.read_csv(data_dir / "m100_synthetic_fault_scenarios.csv")
        seg = df["scenario_id"].astype("category").cat.codes
        split = df["split"].astype(str)
        causal = L.causal_features(df, seg)
        X = causal.drop(columns=["segment_id", "pos_in_segment"])
        # warmup rows lack sufficient causal context
        if task == "multiclass":
            labels = df["synthetic_fault_type"]
            valid = labels.notna() & split.isin(["train", "val", "test"])
            valid &= causal["pos_in_segment"] >= L.WARMUP
            y = labels.astype(str)
        elif task == "binary":
            labels = pd.to_numeric(df["synthetic_label"], errors="coerce")
            valid = labels.notna() & split.isin(["train", "val", "test"])
            valid &= causal["pos_in_segment"] >= L.WARMUP
            y = labels.fillna(0).astype(int)
        else:
            raise ValueError("task must be 'multiclass' or 'binary'")
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

def compute_multiclass_metrics(y_true, y_pred, labels=None):
    if labels is None:
        labels = sorted(list(set(y_true) | set(y_pred)))
    rep = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    macro_f1 = float(np.mean([rep[c]["f1-score"] for c in labels if rep[c]["support"] > 0])) if labels else 0.0
    return {
        'accuracy': float(accuracy_score(y_true, y_pred)),
        'macro_f1_over_classes_present_in_test': round(macro_f1, 4),
        'macro_f1': float(rep.get('macro avg', {}).get('f1-score', 0.0)),
        'weighted_f1': float(rep.get('weighted avg', {}).get('f1-score', 0.0)),
        'macro_precision': float(rep.get('macro avg', {}).get('precision', 0.0)),
        'macro_recall': float(rep.get('macro avg', {}).get('recall', 0.0)),
        'labels': labels,
        'confusion_matrix': cm.tolist(),
        'per_class': {c: {k: round(v, 4) if isinstance(v, float) else v for k, v in rep[c].items()} for c in labels if c in rep},
        'classification_report': rep,
    }
