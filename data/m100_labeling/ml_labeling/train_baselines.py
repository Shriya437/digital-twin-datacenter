"""Baseline supervised experiments on the labeled datasets (chronological splits only).

Reads the CSVs written by build_labeled_dataset.py, recomputes PAST-ONLY features with
labeling.causal_features, trains/evaluates: majority baseline, naive absolute-threshold
baseline, RandomForest, HistGradientBoosting.  Observed-heuristic and synthetic tasks
are evaluated separately.  Usage:
    python ml_labeling/train_baselines.py --data-dir outputs/labeled_dataset
"""
from __future__ import annotations
import argparse, json, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, classification_report,
                             confusion_matrix, precision_recall_curve, precision_recall_fscore_support)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labeling as L
from docs import _md
warnings.filterwarnings("ignore")
SEED = 42
H = L.HORIZON


def feature_table(raw: pd.DataFrame, seg: pd.Series):
    f = L.causal_features(raw, seg)
    return f.drop(columns=["segment_id", "pos_in_segment"]), f["pos_in_segment"]


def models():
    return {
        "RandomForest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight="balanced_subsample", n_jobs=-1, random_state=SEED),
        "HistGB": HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, class_weight="balanced", random_state=SEED),
    }


def best_threshold(y, p):
    if y.sum() == 0: return 0.5
    pr, rc, th = precision_recall_curve(y, p)
    f1 = 2 * pr * rc / np.maximum(pr + rc, 1e-12)
    return float(th[int(np.nanargmax(f1[:-1]))]) if len(th) else 0.5


def bin_metrics(y, p, thr):
    yhat = (p >= thr).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(y, yhat, average="binary", zero_division=0)
    return {"n": int(len(y)), "positives": int(y.sum()), "prevalence": round(float(y.mean()), 4),
            "threshold": round(float(thr), 4), "precision": round(float(pr), 3), "recall": round(float(rc), 3), "f1": round(float(f1), 3),
            "pr_auc": round(float(average_precision_score(y, p)), 3) if y.sum() > 0 else None,
            "brier": round(float(brier_score_loss(y, np.clip(p, 0, 1))), 4),
            "confusion_matrix[[TN,FP],[FN,TP]]": confusion_matrix(y, yhat, labels=[0, 1]).tolist()}


def run_binary(name, Xtr, ytr, Xva, yva, Xte, yte, naive_col, results, curves):
    out = {}
    d = DummyClassifier(strategy="prior").fit(Xtr, ytr)
    out["MajorityClass"] = bin_metrics(yte, d.predict_proba(Xte)[:, 1], 0.5)
    # naive absolute-threshold baseline: raw level above train 95th percentile (knows nothing about load)
    q = float(np.nanquantile(Xtr[naive_col], 0.95))
    s_va, s_te = Xva[naive_col].values, Xte[naive_col].values
    out[f"NaiveThreshold({naive_col}>{q:.1f})"] = bin_metrics(yte, (s_te > q).astype(float), 0.5)
    for mn, m in models().items():
        m.fit(Xtr, ytr)
        pva, pte = m.predict_proba(Xva)[:, 1], m.predict_proba(Xte)[:, 1]
        thr = best_threshold(yva, pva)
        r = bin_metrics(yte, pte, thr); r["val_pr_auc"] = round(float(average_precision_score(yva, pva)), 3) if yva.sum() else None
        if yva.sum() > 0 and len(np.unique(pva)) > 1:     # isotonic calibration fitted on VAL only
            iso = IsotonicRegression(out_of_bounds="clip").fit(pva, yva)
            r["brier_after_isotonic_val_calibration"] = round(float(brier_score_loss(yte, iso.predict(pte))), 4)
        out[mn] = r
        curves[(name, mn)] = (yte.values, pte)
    results[name] = out
    return out


def multiclass(name, Xtr, ytr, Xte, yte, results):
    res = {}
    labels = sorted(set(ytr) | set(yte))
    for mn, m in {"RandomForest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight="balanced_subsample", n_jobs=-1, random_state=SEED),
                  "HistGB": HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, class_weight="balanced", random_state=SEED)}.items():
        m.fit(Xtr, ytr); pred = m.predict(Xte)
        rep = classification_report(yte, pred, labels=labels, output_dict=True, zero_division=0)
        res[mn] = {"macro_f1_over_classes_present_in_test": round(float(np.mean([rep[c]["f1-score"] for c in labels if rep[c]["support"] > 0])), 3),
                   "per_class": {c: {k: round(v, 3) for k, v in rep[c].items()} for c in labels},
                   "labels": labels, "confusion_matrix": confusion_matrix(yte, pred, labels=labels).tolist(),
                   "classes_in_train": sorted(set(ytr)), "classes_in_test": sorted(set(yte))}
    results[name] = res


def main(data_dir: Path):
    obs = pd.read_csv(data_dir / "m100_node1_labeled_observed.csv")
    syn = pd.read_csv(data_dir / "m100_synthetic_fault_scenarios.csv")
    results, curves = {}, {}
    # ---------------- observed features (past-only)
    obs["timestamp_utc"] = pd.to_datetime(obs["timestamp"], utc=True)
    Xo, pos = feature_table(obs, obs["segment_id"])
    evid = [c for c in obs.columns if c.startswith("rule_")]
    Xo_leak = pd.concat([Xo, obs[evid]], axis=1)
    sp = obs["split"]
    # T1 current-time anomaly (heuristic)
    ok = (obs["label_valid"] == 1)
    y1 = obs["anomaly_label"]
    def sub(X, mask_ok, y):
        return [(X[(sp == s) & mask_ok], y[(sp == s) & mask_ok].astype(int)) for s in ("train", "val", "test")]
    (a, ya), (b, yb), (c, yc) = sub(Xo, ok, y1)
    run_binary("T1_observed_anomaly_label__causal_features", a, ya, b, yb, c, yc, "temp_max", results, curves)
    (a2, ya2), (b2, yb2), (c2, yc2) = sub(Xo_leak, ok, y1)
    run_binary("T1b_observed_anomaly_label__WITH_rule_evidence_LEAKAGE_CHECK", a2, ya2, b2, yb2, c2, yc2, "temp_max", results, curves)
    # random split illustration (INVALID protocol)
    from sklearn.model_selection import train_test_split
    Xr, yr = Xo[ok & sp.isin(["train", "val", "test"])], y1[ok & sp.isin(["train", "val", "test"])].astype(int)
    Xa, Xb, ya_, yb_ = train_test_split(Xr, yr, test_size=0.3, random_state=SEED, stratify=yr)
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, class_weight="balanced", random_state=SEED).fit(Xa, ya_)
    results["T1_INVALID_random_row_split_illustration"] = {"HistGB": bin_metrics(yb_, m.predict_proba(Xb)[:, 1], 0.5),
        "WARNING": "random row split of overlapping 20 s windows; neighbouring rows leak across train/test. Shown only to quantify inflation. Do NOT cite."}
    # T2 future anomaly within horizon, onset subset (current label == 0)
    fcol = f"anomaly_within_next_{H}"
    ok2 = (obs["anomaly_label"] == 0) & obs[fcol].notna()
    (a, ya), (b, yb), (c, yc) = sub(Xo, ok2, obs[fcol])
    run_binary(f"T2_observed_future_anomaly_next{H}_onset_subset", a, ya, b, yb, c, yc, "temp_max", results, curves)
    # T3 multiclass heuristic fault_type
    okm = ok & (obs["fault_type"] != "ambiguous_unknown")
    multiclass("T3_observed_fault_type_multiclass", Xo[(sp == "train") & okm], obs.loc[(sp == "train") & okm, "fault_type"],
               Xo[(sp == "test") & okm], obs.loc[(sp == "test") & okm, "fault_type"], results)
    # ---------------- synthetic features: each scenario is its own segment
    sid = syn["scenario_id"].astype("category").cat.codes
    Xs, spos = feature_table(syn, sid)
    oks = spos >= L.WARMUP
    ss = syn["split"]
    def subs(mask, y):
        return [(Xs[(ss == s) & mask], y[(ss == s) & mask]) for s in ("train", "val", "test")]
    (a, ya), (b, yb), (c, yc) = subs(oks, syn["synthetic_label"].astype(int))
    run_binary("S1_synthetic_label__binary", a, ya, b, yb, c, yc, "temp_max", results, curves)
    okf = oks & syn[f"synthetic_anomaly_within_next_{H}"].notna() & (syn["synthetic_label"] == 0)
    (a, ya), (b, yb), (c, yc) = subs(okf, syn[f"synthetic_anomaly_within_next_{H}"].fillna(0).astype(int))
    run_binary(f"S2_synthetic_future_anomaly_next{H}_onset_subset", a, ya, b, yb, c, yc, "temp_max", results, curves)
    multiclass("S3_synthetic_fault_type_multiclass", Xs[(ss == "train") & oks], syn.loc[(ss == "train") & oks, "synthetic_fault_type"],
               Xs[(ss == "test") & oks], syn.loc[(ss == "test") & oks, "synthetic_fault_type"], results)
    # ---------------- cross-domain: train on SYNTHETIC (train), evaluate on OBSERVED heuristic labels (test)
    (a, ya), (b, yb), _ = subs(oks, syn["synthetic_label"].astype(int))
    res = {}
    m = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, class_weight="balanced", random_state=SEED).fit(a, ya)
    thr = best_threshold(yb, m.predict_proba(b)[:, 1])
    ptest = m.predict_proba(Xo[(sp == "test") & ok])[:, 1]
    res["HistGB(synthetic-train -> observed-test)"] = bin_metrics(y1[(sp == "test") & ok].astype(int), ptest, thr)
    results["X1_cross_domain_synthetic_to_observed_heuristic"] = res
    (data_dir / "model_results.json").write_text(json.dumps(results, indent=2, default=str))
    write_md(data_dir, results); plot_pr(data_dir, curves)
    return results


def write_md(data_dir, R):
    md = ["# Baseline model results (chronological splits; all labels are heuristic proxies or simulation truth)\n",
          "Protocol: train rows -> fit; val rows -> threshold (max-F1) and isotonic calibration; test rows -> report. 30-row purge at split cuts. Features are past-only within a segment/scenario. "
          "Positive classes are tiny (see `positives`), so every number has wide uncertainty; treat as sanity checks, not performance claims.\n"]
    for k, v in R.items():
        md.append(f"\n## {k}\n")
        if "WARNING" in v: md.append(f"**{v['WARNING']}**\n")
        first = next(iter(v.values()))
        if isinstance(first, dict) and "precision" in first:
            rows = []
            for mn, r in v.items():
                if not isinstance(r, dict): continue
                rows.append({"model": mn, **{kk: r[kk] for kk in ["n", "positives", "threshold", "precision", "recall", "f1", "pr_auc", "brier"]},
                             "brier_isotonic": r.get("brier_after_isotonic_val_calibration"), "CM [[TN,FP],[FN,TP]]": str(r["confusion_matrix[[TN,FP],[FN,TP]]"])})
            md.append(_md(pd.DataFrame(rows), index=False))
        elif isinstance(first, dict) and "per_class" in first:
            for mn, r in v.items():
                md.append(f"**{mn}** macro-F1 (classes present in test): {r['macro_f1_over_classes_present_in_test']}; train classes {r['classes_in_train']}; test classes {r['classes_in_test']}")
                md.append("```\nlabels: " + str(r["labels"]) + "\n" + "\n".join(map(str, r["confusion_matrix"])) + "\n```")
                md.append(_md(pd.DataFrame(r["per_class"]).T))
    (data_dir / "model_results.md").write_text("\n".join(md))


def plot_pr(data_dir, curves):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    keys = sorted({k[0] for k in curves}); fig, ax = plt.subplots(1, len(keys), figsize=(4.6 * len(keys), 4), squeeze=False)
    for a, k in zip(ax[0], keys):
        for (n, mn), (y, p) in curves.items():
            if n == k and y.sum() > 0:
                pr, rc, _ = precision_recall_curve(y, p); a.plot(rc, pr, label=f"{mn} (AP={average_precision_score(y, p):.2f})")
        a.axhline(np.mean(y), ls=":", color="grey"); a.set_title(k.replace("__", "\n"), fontsize=7); a.set_xlabel("recall"); a.set_ylabel("precision"); a.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(data_dir / "figures" / "pr_curves_test.png", dpi=120); plt.close(fig)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(); ap.add_argument("--data-dir", default=str(base / "outputs" / "labeled_dataset"))
    main(Path(ap.parse_args().data_dir))
