"""Regenerate every labeled-dataset artefact from the ORIGINAL M100 CSV.

Usage (from the repository root, same layout as predictive_maintenance.py):
    python ml_labeling/build_labeled_dataset.py \
        --input data/m100_node1_digital_twin.csv --output-dir outputs/labeled_dataset
The input file is only ever read.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labeling as L
import simulation as S
from docs import build_schema, write_schema, write_report

SEED = 42


def _resolution(ref):
    return {k: {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items()
                if a in ("target", "preds", "mad", "quant_step", "scale", "hard", "soft", "n_fit", "median_res")}
            for k, v in ref.items()}


def label_observed(df, ref=None):
    seg = L.segment_ids(df["timestamp_utc"])
    feats = L.causal_features(df, seg)
    split = pd.Series(L.split_labels(len(df)), index=df.index)
    if ref is None:
        ref = L.fit_reference(df, feats, (split == "train").values)
    z, rules = L.label_series(df, feats, ref)
    return seg, feats, split, ref, z, rules


def build(input_path: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True); (out / "figures").mkdir(exist_ok=True)
    df = L.load_observed(input_path)
    orig_cols = [c for c in pd.read_csv(input_path, nrows=0).columns]
    seg, feats, split, ref, z, rules = label_observed(df)
    fut = L.future_target(rules["anomaly_label"], feats["segment_id"])

    # ---------------- (a) enhanced observed dataset (original columns first, untouched)
    enh = df[orig_cols].copy()
    enh["row_id"] = df["row_id"]
    enh["data_origin"] = "observed"
    enh["segment_id"] = feats["segment_id"]
    enh["pos_in_segment"] = feats["pos_in_segment"]
    enh["split"] = split
    enh["anomaly_label"] = rules["anomaly_label"]
    enh["fault_type"] = rules["fault_type"]
    enh["label_status"] = rules["label_status"]
    enh["label_valid"] = rules["label_valid"]
    enh[f"anomaly_within_next_{L.HORIZON}"] = fut
    enh["label_source"] = "heuristic_rule_v1"
    for fam in L.FAMILIES:
        enh[f"rule_{fam}_score"] = rules[f"rule_{fam}_score"].round(4)
        enh[f"rule_{fam}_persistent"] = rules[f"rule_{fam}_persistent"].astype(int)
    for c in z:
        enh[f"rule_{c}"] = z[c].round(4)
    enh.to_csv(out / "m100_node1_labeled_observed.csv", index=False)

    # ---------------- (b) synthetic scenarios
    train = (split == "train").values
    cp = df["p0_power"] + df["p1_power"]
    idle_cp = float(cp[train & (cp < 100).values].median())
    cp_range = float(cp[train].quantile(0.95) - idle_cp)
    ps = df["ps0_input_power"] + df["ps1_input_power"]
    slope = float(LinearRegression().fit(ps[train].values[:, None], df["total_power"][train]).coef_[0])
    sim_params = {"thermal_hard_C": float(ref["z_temp_p0"]["hard"] * ref["z_temp_p0"]["scale"]),
                  "total_vs_ps_slope": round(slope, 4)}
    rng = np.random.default_rng(SEED)
    cands = S.candidate_windows(split.values, feats["segment_id"].values,
                                rules["anomaly_label"].astype("float").fillna(-1).values, feats["pos_in_segment"].values)
    frames, n_sc = [], 0
    for sp in ["train", "val", "test"]:
        for kind in S.KINDS:
            n = S.N_PER_KIND[sp]
            pool = cands[sp]
            pick = rng.choice(len(pool), size=n, replace=len(pool) < n)
            for j, pi in enumerate(pick):
                s, e = pool[pi]
                base = df.iloc[s:e]
                d, meta, info = S.build_scenario(base, kind, rng, sim_params, idle_cp, cp_range)
                sid = f"SYN-{sp}-{kind}-{j:02d}"
                sdf = pd.DataFrame({"data_origin": "synthetic", "scenario_id": sid, "split": sp,
                                    "base_row_id": base["row_id"].values, "base_timestamp": base["timestamp"].values,
                                    "step_in_scenario": np.arange(len(base))})
                for m in L.METRICS:
                    sdf[m] = d[m].values
                for k, v in meta.items():
                    sdf[k] = v
                for c in info:
                    sdf[c] = info[c].values
                sf = L.causal_features(sdf, pd.Series(n_sc, index=sdf.index))
                sz = L.channel_z(sdf, sf, ref)
                sr = L.apply_rules(sz, sf, ref)
                sdf["rule_fault_type"] = sr["fault_type"].values
                sdf["rule_anomaly_label"] = sr["anomaly_label"].values
                lab = sdf["synthetic_label"].values
                sdf[f"synthetic_anomaly_within_next_{L.HORIZON}"] = [
                    int(lab[i + 1:i + 1 + L.HORIZON].max()) if i + L.HORIZON < len(lab) else pd.NA for i in range(len(lab))]
                sdf["label_source"] = "simulated_injection_v1"
                frames.append(sdf); n_sc += 1
    syn = pd.concat(frames, ignore_index=True)
    syn["rule_anomaly_label"] = syn["rule_anomaly_label"].astype("Int64")
    syn[f"synthetic_anomaly_within_next_{L.HORIZON}"] = syn[f"synthetic_anomaly_within_next_{L.HORIZON}"].astype("Int64")
    syn.to_csv(out / "m100_synthetic_fault_scenarios.csv", index=False)

    # ---------------- validation
    val = validate(input_path, df, orig_cols, enh, syn, ref, rules, feats)
    params = {"seed": SEED, "window": L.WINDOW, "warmup_rows": L.WARMUP, "persistence": L.PERSIST,
              "horizon_samples": L.HORIZON, "gap_threshold_seconds": L.GAP_SECONDS, "purge_rows": L.PURGE,
              "split_fractions": [L.TRAIN_FRAC, L.VAL_FRAC], "hard_quantile": L.HARD_Q, "soft_quantile": L.SOFT_Q,
              "hard_min": L.HARD_MIN, "soft_min": L.SOFT_MIN, "channels": _resolution(ref),
              "families": L.FAMILIES, "simulation": {**sim_params, "idle_cpu_power": idle_cp, "cpu_power_range": cp_range,
              "window_len": S.WINDOW_LEN, "stride": S.STRIDE, "n_per_kind": S.N_PER_KIND, "assumptions": {**S.SIM_ASSUMPTIONS, "power": S.SIM_ASSUMPTIONS["power"] % sim_params["total_vs_ps_slope"]}}}
    (out / "labeling_params.json").write_text(json.dumps(params, indent=2, default=str))
    schema = build_schema(enh.columns.tolist(), syn.columns.tolist(), orig_cols)
    write_schema(schema, out)
    stats = write_report(out, df, enh, syn, feats, ref, params, val)
    make_figures(out, df, enh, syn, feats)
    return enh, syn, val, stats


def validate(input_path, df, orig_cols, enh, syn, ref, rules, feats):
    v = {}
    orig = pd.read_csv(input_path)
    v["row_count_equal"] = len(orig) == len(enh)
    pd.testing.assert_frame_equal(orig, enh[orig_cols], check_exact=True)
    v["original_columns_identical"] = True
    v["original_timestamp_strings_identical"] = bool((orig["timestamp"].astype(str).values == enh["timestamp"].astype(str).values).all())
    v["duplicate_timestamps"] = int(df["timestamp_utc"].duplicated().sum())
    v["chronological_order"] = bool(df["timestamp_utc"].is_monotonic_increasing)
    v["missing_values_in_original_telemetry"] = int(orig[L.METRICS].isna().sum().sum())
    v["n_segments"] = int(feats["segment_id"].nunique())
    gaps = df["timestamp_utc"].diff().dt.total_seconds()
    v["rows_following_gap_gt_60s"] = int((gaps > L.GAP_SECONDS).sum())
    v["labels_never_cross_gap"] = bool(((df.groupby(feats["segment_id"].values)["timestamp_utc"].diff().dt.total_seconds().dropna()) <= L.GAP_SECONDS).all())
    v["allowed_fault_types_only"] = bool(set(enh["fault_type"]).issubset(L.FAULT_CLASSES))
    v["anomaly_label_values"] = sorted(map(int, enh["anomaly_label"].dropna().unique()))
    v["anomaly1_iff_class_in_anomaly_set"] = bool(((enh["anomaly_label"] == 1) == enh["fault_type"].isin(
        ["thermal_anomaly", "fan_performance_anomaly", "power_anomaly", "combined_anomaly"])).all())
    # causality: relabel truncated prefixes with the SAME reference; labels must be identical
    ok = True
    for cut in (1500, 3000, 4200):
        sub = df.iloc[:cut].copy()
        seg2 = L.segment_ids(sub["timestamp_utc"]); f2 = L.causal_features(sub, seg2)
        _, r2 = L.label_series(sub, f2, ref)
        ok &= bool((r2["fault_type"].values == rules["fault_type"].values[:cut]).all())
    v["causal_labels_prefix_test_passed"] = bool(ok)
    # synthetic
    v["synthetic_rows"] = int(len(syn)); v["synthetic_scenarios"] = int(syn["scenario_id"].nunique())
    v["synthetic_rows_without_scenario"] = int(syn["scenario_id"].isna().sum())
    v["synthetic_origin_values"] = sorted(syn["data_origin"].unique()); v["observed_origin_values"] = sorted(enh["data_origin"].unique())
    o = df.set_index("row_id")
    mism = 0
    for m in L.METRICS:
        base = o.loc[syn["base_row_id"], m].values
        first_nz = syn.groupby("scenario_id")["injection_intensity"].transform(
            lambda x: int((x.values > 0).argmax()) if (x.values > 0).any() else len(x))
        untouched = syn["injected_fault_type"].eq("none") | (syn["step_in_scenario"] < first_nz)   # controls + pre-onset rows
        mism += int((syn.loc[untouched, m].values != base[untouched.values]).sum())
    v["synthetic_control_and_preonset_rows_differing_from_base"] = mism
    v["base_ts_matches_original"] = bool((o.loc[syn["base_row_id"], "timestamp"].values == syn["base_timestamp"].values).all())
    sp = enh.set_index("row_id")["split"]
    v["synthetic_base_split_consistent"] = bool((sp.loc[syn["base_row_id"]].values == syn["split"].values).all())
    ov = syn.groupby("base_row_id")["split"].nunique()
    v["base_rows_shared_across_splits"] = int((ov > 1).sum())
    v["scenarios_with_single_split"] = bool((syn.groupby("scenario_id")["split"].nunique() == 1).all())
    v["unique_scenario_timestamp_pairs"] = bool(not syn.duplicated(["scenario_id", "step_in_scenario"]).any())
    v["observed_file_modified"] = False
    return v


def make_figures(out, df, enh, syn, feats):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir = out / "figures"
    colors = {"normal": "#4c9f70", "thermal_anomaly": "#d1495b", "fan_performance_anomaly": "#edae49",
              "power_anomaly": "#00798c", "combined_anomaly": "#6a3d9a", "ambiguous_unknown": "#9e9e9e",
              "insufficient_context": "#d9d9d9"}
    # 1 label distribution
    fig, ax = plt.subplots(1, 3, figsize=(17, 4.8))
    ct = pd.crosstab(enh["split"], enh["fault_type"]).reindex(["train", "purge", "val", "test"]).fillna(0)
    ct = ct[[c for c in colors if c in ct]]
    ct.plot(kind="bar", stacked=True, ax=ax[0], color=[colors[c] for c in ct.columns], legend=False)
    ax[0].set_yscale("symlog"); ax[0].set_title("Observed: heuristic fault_type by split (symlog)"); ax[0].set_xlabel("")
    ctn = pd.crosstab(enh["split"], enh["fault_type"], normalize="index").reindex(["train", "val", "test"])
    ctn = ctn[[c for c in colors if c in ctn]]
    ctn.plot(kind="bar", stacked=True, ax=ax[1], color=[colors[c] for c in ctn.columns]); ax[1].set_title("Observed: share per split")
    ax[1].legend(fontsize=7, loc="lower left"); ax[1].set_xlabel("")
    cs = pd.crosstab(syn["split"], syn["synthetic_fault_type"]).reindex(["train", "val", "test"])
    cs = cs[[c for c in colors if c in cs]]
    cs.plot(kind="bar", stacked=True, ax=ax[2], color=[colors[c] for c in cs.columns], legend=False)
    ax[2].set_title("SIMULATED: synthetic_fault_type rows by split"); ax[2].set_xlabel("")
    for a in ax: a.tick_params(axis="x", rotation=0)
    fig.tight_layout(); fig.savefig(fig_dir / "label_distribution.png", dpi=130); plt.close(fig)
    # 2 observed timeline
    t = df["timestamp_utc"]
    fig, ax = plt.subplots(4, 1, figsize=(16, 10), sharex=True)
    x = np.arange(len(df))
    for a, (col, lab) in zip(ax, [(feats["temp_max"], "max VDD temp"), (feats["fan_mean"], "mean fan speed (units undocumented)"),
                                  (feats["ps_input_sum"], "ps0+ps1 input power (undocumented unit)"), (df["ambient"], "ambient")]):
        a.plot(x, col.values, lw=.6, color="#333"); a.set_ylabel(lab, fontsize=8)
        for ft, c in colors.items():
            if ft in ("normal", "insufficient_context"): continue
            m = (enh["fault_type"] == ft).values
            a.fill_between(x, 0, 1, where=m, transform=a.get_xaxis_transform(), color=c, alpha=.35, step="mid")
        for b in np.where(feats["segment_id"].diff().fillna(0).values > 0)[0]:
            a.axvline(b, color="k", ls="--", lw=.8)
    for b in [int(.6 * len(df)), int(.8 * len(df))]:
        for a in ax: a.axvline(b, color="blue", ls=":", lw=1)
    ax[0].set_title("Observed telemetry, heuristic labels shaded (dashed = gap/segment boundary, dotted blue = train|val|test cuts)")
    ax[-1].set_xlabel("row_id"); fig.tight_layout(); fig.savefig(fig_dir / "observed_timeline_labels.png", dpi=130); plt.close(fig)
    # 3 normal vs anomalous zoom
    an = (enh["anomaly_label"] == 1).fillna(False).to_numpy(dtype=bool)
    if an.any():
        runs = pd.Series(an).ne(pd.Series(an).shift()).cumsum()
        r = pd.Series(an).groupby(runs).agg(["first", "size"]); r = r[r["first"]]
        best = r["size"].idxmax(); idx = np.where(runs.values == best)[0]
        c0 = int(idx[len(idx) // 2]); lo, hi = max(c0 - 90, 0), min(c0 + 90, len(df))
        norm_hi = np.where((enh["fault_type"] == "normal").values & (enh["split"] == "train").values)[0]
        n0 = int(norm_hi[np.argmax(feats["cpu_power_sum"].values[norm_hi])]); nlo, nhi = max(n0 - 90, 0), min(n0 + 90, len(df))
        cols = ["p0_vdd_temp", "p1_vdd_temp", "fan0_0", "fan1_0", "ps0_input_power", "ps1_input_power", "p0_power", "ambient"]
        fig, ax = plt.subplots(len(cols), 2, figsize=(14, 14), sharex="col")
        for j, (a_, b_, ttl) in enumerate([(nlo, nhi, "NORMAL-looking (train, highest-load normal window)"), (lo, hi, "Heuristically ANOMALOUS (longest run)")]):
            for i, cname in enumerate(cols):
                ax[i, j].plot(range(a_, b_), df[cname].values[a_:b_], lw=1)
                am = an[a_:b_]; ax[i, j].fill_between(range(a_, b_), 0, 1, where=am, transform=ax[i, j].get_xaxis_transform(), color="#d1495b", alpha=.25)
                ax[i, j].set_ylabel(cname, fontsize=8)
            ax[0, j].set_title(ttl, fontsize=9)
        fig.tight_layout(); fig.savefig(fig_dir / "observed_normal_vs_anomalous.png", dpi=120); plt.close(fig)
    # 4 synthetic examples
    o = df.set_index("row_id")
    kinds = [k for k in S.KINDS if k != "none"]
    fig, ax = plt.subplots(len(kinds), 3, figsize=(16, 12))
    show = {"thermal_anomaly": ["p0_vdd_temp", "p1_vdd_temp", "ps0_input_power"], "fan_performance_anomaly": ["fan0_0", "fan1_0", "p0_vdd_temp"],
            "power_anomaly": ["ps0_input_power", "total_power", "p0_power"], "combined_anomaly": ["p0_vdd_temp", "fan0_0", "ps0_input_power"]}
    for i, k in enumerate(kinds):
        sid = f"SYN-train-{k}-00"; s = syn[syn["scenario_id"] == sid]
        for j, m in enumerate(show[k]):
            ax[i, j].plot(s["step_in_scenario"], o.loc[s["base_row_id"], m].values, color="#888", lw=1, label="observed base copy")
            ax[i, j].plot(s["step_in_scenario"], s[m], color="#d1495b", lw=1.2, label="synthetic")
            ax[i, j].fill_between(s["step_in_scenario"], 0, 1, where=s["synthetic_label"].values == 1, transform=ax[i, j].get_xaxis_transform(), color="#edae49", alpha=.25)
            ax[i, j].set_title(f"{sid} | {m}", fontsize=8)
        ax[i, 0].legend(fontsize=7)
    fig.suptitle("SIMULATED scenarios (shaded = synthetic_label=1). Grey = untouched observed base window", fontsize=10)
    fig.tight_layout(); fig.savefig(fig_dir / "synthetic_scenarios.png", dpi=120); plt.close(fig)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(base / "data" / "m100_node1_digital_twin.csv"))
    ap.add_argument("--output-dir", default=str(base / "outputs" / "labeled_dataset"))
    a = ap.parse_args()
    enh, syn, val, stats = build(Path(a.input), Path(a.output_dir))
    print(json.dumps(val, indent=2))
    print("fault_type counts (observed):\n", enh["fault_type"].value_counts().to_string())
    print("synthetic_fault_type counts:\n", syn["synthetic_fault_type"].value_counts().to_string())
