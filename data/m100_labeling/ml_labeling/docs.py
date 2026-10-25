"""Data dictionary + labeling report writers."""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import labeling as L

H = L.HORIZON
CLS = "normal | thermal_anomaly | fan_performance_anomaly | power_anomaly | combined_anomaly | ambiguous_unknown | insufficient_context"
ORIG_DESC = {
    "timestamp": "Original timestamp string (UTC, ~20 s sampling).",
    "ambient": "Ambient temperature reading. Unit undocumented in the source (values 18.8-37.0, consistent with deg C but NOT confirmed).",
    "p0_vdd_temp": "Processor 0 VDD temperature (values 28-52; deg C presumed, unit undocumented). Integer resolution.",
    "p1_vdd_temp": "Processor 1 VDD temperature (values 27-47; deg C presumed). Integer resolution.",
    "fan0_0": "Fan 0 speed (values 4200-10100; RPM presumed, unit undocumented). 100-step resolution.",
    "fan1_0": "Fan 1 speed (values 4300-9800; RPM presumed, unit undocumented).",
    "p0_power": "Processor 0 power (values 32-168; W presumed, unit undocumented).",
    "p1_power": "Processor 1 power (values 26-162; W presumed).",
    "ps0_input_power": "Power supply 0 input power (values 250-980; W presumed).",
    "ps1_input_power": "Power supply 1 input power (values 270-1020; W presumed).",
    "total_power": "Node total power (values 400-1760). Relation to other power columns is undocumented (not the sum of any obvious subset).",
    "gap_seconds": "Original column: seconds since previous row (blank on first row).",
    "telemetry_gap": "Original column: True where a timestamp gap was flagged by the upstream pipeline.",
    "has_missing_metric": "Original column: True if any metric was missing upstream (always False here).",
}


def _spec():
    o, d, s = "observed", "derived_heuristic", "simulated"
    E = {}
    def a(col, origin, typ, allowed, desc, method="", ds="observed"):
        E[(ds, col)] = dict(dataset=ds, column=col, origin=origin, dtype=typ, allowed_values=allowed, description=desc, generation_method=method)
    a("row_id", "provenance", "int", "0..n-1", "0-based position of the row in the ORIGINAL CSV file; join key back to the source.", "enumerate original rows")
    a("data_origin", "provenance", "str", "observed | synthetic", "Whether the row is real telemetry or simulated.", "constant per file")
    a("segment_id", d, "int", "1..K", "Continuous-segment id: new segment whenever the gap to the previous row exceeds 60 s (rule from feature_engineering_1.py: max(3*median interval, 60 s)). Labels/features never cross segments.", "cumulative count of gaps > 60 s")
    a("pos_in_segment", d, "int", ">=0", "0-based position within the segment (rows of history available).", "groupby segment cumcount")
    a("split", d, "str", "train | purge | val | test", "Chronological 60/20/20 split by row order; 30 rows (window 15 + horizon 15) after each cut are 'purge' and must not be used for fit or evaluation.", "row index thresholds")
    a("anomaly_label", d, "Int64 (nullable)", "0 | 1 | blank", "HEURISTIC PROXY (not a verified fault). 1 = a rule family exceeded its hard threshold for 3 consecutive samples; 0 = no family exceeded even the soft threshold; blank = ambiguous or insufficient context.", "see labeling_report.md; causal rules, thresholds fitted on train only")
    a("fault_type", d, "str", CLS, "HEURISTIC class of the evidence. single family -> thermal/fan/power; >=2 families persistent -> combined_anomaly; soft-only/non-persistent evidence -> ambiguous_unknown; first 14 rows of each segment -> insufficient_context.", "rule combination")
    a("label_status", d, "str", "confident_normal | rule_triggered | ambiguous | insufficient_context", "Why the row has its label.", "derived from fault_type")
    a("label_valid", d, "int", "0 | 1", "1 iff anomaly_label is not blank. Use label_valid==1 rows for binary supervised training/evaluation.", "anomaly_label.notna()")
    a(f"anomaly_within_next_{H}", d, "Int64 (nullable)", "0 | 1 | blank", f"FUTURE-LOOKING TARGET: 1 if any of the next {H} rows (~5 min) in the same segment has anomaly_label==1; 0 if all are 0; blank if the horizon exits the segment or contains blank labels. Never use as a feature.", "forward window over anomaly_label")
    a("label_source", "provenance", "str", "heuristic_rule_v1 | simulated_injection_v1", "Provenance of the label columns.", "constant")
    for fam in L.FAMILIES:
        a(f"rule_{fam}_score", d, "float", ">=0", f"Evidence for the {fam} family: max over its channels of (|z| / hard threshold). >=1 means hard threshold exceeded at that row. LABEL EVIDENCE - do not use as ML features (leakage).", "residual vs train-fitted reference")
        a(f"rule_{fam}_persistent", d, "int", "0 | 1", f"1 if the {fam} hard threshold was exceeded in the current and 2 previous samples.", "trailing rolling min of exceedance")
    zdesc = {"z_temp_p0": "P0 temperature residual vs load/ambient reference (upper tail only)", "z_temp_p1": "P1 temperature residual (upper tail)",
             "z_temp_gradient": "|P0-P1 temperature difference| residual vs load", "z_fan_level": "|mean fan speed residual| vs monotone temp/load reference",
             "z_fan_mismatch": "|fan0-fan1|/mean fan, upper tail", "z_ps_total": "|ps0+ps1 residual| vs CPU-power reference", "z_ps_balance": "|ps0-ps1 residual| vs ps total"}
    for k, v in zdesc.items():
        a(f"rule_{k}", d, "float", ">=0 (z_temp_p*, z_fan_mismatch one-sided: may be negative)", f"Robust standardised residual: {v}. LABEL EVIDENCE - leakage if used as feature.", "(observed - train-fitted reference - median)/max(MAD, sensor resolution)")
    S_ = "synthetic"
    for col in ["data_origin", "label_source"]:
        a(col, "provenance", "str", "synthetic" if col == "data_origin" else "simulated_injection_v1", "Provenance.", "constant", S_)
    a("scenario_id", "simulated", "str", "SYN-<split>-<kind>-<nn>", "Unique id of the simulated scenario; every synthetic row has one.", "scenario counter", S_)
    a("split", "simulated", "str", "train | val | test", "Split of the observed base window; whole scenarios never cross splits.", "inherited from base rows", S_)
    a("base_row_id", "provenance", "int", "row_id in observed file", "Row of the original CSV that this synthetic row was copied from.", "copy", S_)
    a("base_timestamp", "provenance", "str", "original timestamp", "Original timestamp of the base row (NOT a simulated time; repeated across scenarios).", "copy", S_)
    a("step_in_scenario", "simulated", "int", "0..179", "Position within the scenario (acts as its own segment).", "enumerate", S_)
    a("injected_fault_type", "simulated", "str", "none | thermal_anomaly | fan_performance_anomaly | power_anomaly | combined_anomaly", "Scenario-level injected fault kind (none = control copy of observed window).", "scenario design", S_)
    a("injected_components", "simulated", "str", "none or '+'-joined components", "Which components were injected.", "scenario design", S_)
    a("injection_profile", "simulated", "str", "none | <component>:gradual|abrupt|spike", "Temporal shape per component.", "scenario design", S_)
    a("injection_params", "simulated", "str", "python dict repr", "Sampled magnitude parameters (k, amplitude, deficit, relative increase).", "random draw, seed 42", S_)
    a("synthetic_label", "simulated", "int", "0 | 1", "SIMULATION GROUND TRUTH (true only inside the simulation): 1 while injection intensity >= 0.20.", "injection profile", S_)
    a("synthetic_fault_type", "simulated", "str", "normal | thermal_anomaly | fan_performance_anomaly | power_anomaly | combined_anomaly", "Row-level injected class (combined when >=2 components are active).", "injection profile", S_)
    a("synthetic_severity_stage", "simulated", "int", "0..3", "Injected-effect intensity stage (0<0.2,1<0.5,2<0.9,3>=0.9; abrupt faults jump to 3). NOT remaining useful life or time-to-failure.", "injection profile", S_)
    a("injection_intensity", "simulated", "float", "0..1", "Normalised injection profile m(t) (max over components).", "injection profile", S_)
    a("rule_fault_type", d, "str", CLS, "The observed-data heuristic labeler applied to the synthetic rows (for rule-vs-injection agreement only).", "apply_rules with train reference", S_)
    a("rule_anomaly_label", d, "Int64 (nullable)", "0 | 1 | blank", "Heuristic anomaly_label on synthetic rows.", "apply_rules", S_)
    a(f"synthetic_anomaly_within_next_{H}", "simulated", "Int64 (nullable)", "0 | 1 | blank", f"1 if synthetic_label==1 at any of the next {H} steps of the scenario; blank near the end.", "forward window over synthetic_label", S_)
    for m in L.METRICS:
        a(m, "simulated", "number", "see description", ORIG_DESC[m] + " (SYNTHETIC: a copy of the base row, modified only where the scenario injects a fault)", "copy + injection", S_)
    return E


def build_schema(obs_cols, syn_cols, orig_cols):
    E = _spec(); rows = []
    for col in obs_cols:
        if col in orig_cols:
            rows.append(dict(dataset="observed", column=col, origin="observed", dtype="as in source", allowed_values="as in source", description=ORIG_DESC.get(col, ""), generation_method="UNCHANGED from the original CSV"))
        else:
            rows.append(E[("observed", col)])
    for col in syn_cols:
        rows.append(E.get(("synthetic", col)) or E[("observed", col)] | {"dataset": "synthetic"})
    return pd.DataFrame(rows)


def write_schema(schema, out):
    schema.to_csv(out / "label_schema.csv", index=False)
    md = ["# Label schema / data dictionary\n",
          "Origin legend: **observed** = untouched source telemetry; **derived_heuristic** = rule-based proxy labels/evidence computed from observed telemetry (NOT ground truth); **simulated** = explicitly synthetic; **provenance** = bookkeeping.\n"]
    for ds in ["observed", "synthetic"]:
        md.append(f"\n## {ds} dataset ({'m100_node1_labeled_observed.csv' if ds == 'observed' else 'm100_synthetic_fault_scenarios.csv'})\n")
        md.append("| column | origin | dtype | allowed values | description | generation method |\n|---|---|---|---|---|---|")
        for r in schema[schema.dataset == ds].itertuples():
            md.append(f"| `{r.column}` | {r.origin} | {r.dtype} | {str(r.allowed_values).replace('|', '/')} | {r.description.replace('|', '/')} | {r.generation_method.replace('|', '/')} |")
    (out / "label_schema.md").write_text("\n".join(md))


def _pct(s):
    vc = s.value_counts(dropna=False); return pd.DataFrame({"count": vc, "percent": (100 * vc / len(s)).round(2)})


def _md(df, index=True):
    """Markdown table; falls back to a code block when the optional 'tabulate' package is absent."""
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return "```\n" + df.to_string(index=index) + "\n```"


def write_report(out, df, enh, syn, feats, ref, params, val):
    ts = df["timestamp_utc"]; gaps = ts.diff().dt.total_seconds()
    segs = df.assign(seg=feats["segment_id"].values).groupby("seg").agg(start=("timestamp", "first"), end=("timestamp", "last"), rows=("row_id", "size"))
    segs["duration_min"] = ((pd.to_datetime(segs.end, utc=True) - pd.to_datetime(segs.start, utc=True)).dt.total_seconds() / 60).round(1)
    segs["usable_labeled_rows"] = enh.groupby("segment_id")["label_valid"].sum()
    big = df.assign(gap=gaps)[gaps > L.GAP_SECONDS][["row_id", "timestamp", "gap"]].rename(columns={"gap": "gap_seconds_before_row"})
    intervals = gaps.value_counts().sort_index().rename("rows").to_frame(); intervals.index.name = "interval_seconds"
    cls = pd.crosstab(enh["fault_type"], enh["split"], margins=True)
    clsp = (100 * pd.crosstab(enh["fault_type"], enh["split"], normalize="columns")).round(2)
    anom = pd.crosstab(enh["anomaly_label"].astype("object").fillna("blank"), enh["split"], margins=True)
    fut = pd.crosstab(enh[f"anomaly_within_next_{H}"].astype("object").fillna("blank"), enh["split"], margins=True)
    futc = enh[(enh["anomaly_label"] == 0)]; fut_on = pd.crosstab(futc[f"anomaly_within_next_{H}"].astype("object").fillna("blank"), futc["split"])
    miss = pd.DataFrame({"missing_in_file": df.isna().sum(), "pct": (100 * df.isna().mean()).round(3)}).loc[lambda x: x.index.isin([*L.METRICS, "gap_seconds", "timestamp"])]
    lab_miss = enh[["anomaly_label", "fault_type", f"anomaly_within_next_{H}"]].isna().sum().to_frame("blank_or_NA")
    _sc = syn.drop_duplicates("scenario_id"); syn_cnt = pd.crosstab(_sc["injected_fault_type"], _sc["split"], margins=True)
    syn_rows = pd.crosstab(syn["synthetic_fault_type"], syn["split"], margins=True)
    syn_stage = pd.crosstab(syn["synthetic_severity_stage"], syn["split"], margins=True)
    ok = syn[(syn["rule_anomaly_label"].notna())]
    act = ok[ok.synthetic_label == 1]; ctl = ok[ok.injected_fault_type == "none"]; pre = ok[(ok.synthetic_label == 0) & (ok.injected_fault_type != "none")]
    agree = act.groupby("synthetic_fault_type")["rule_anomaly_label"].agg(rows="size", rule_recall="mean").round(3)
    agree.loc["ALL injected-active"] = [len(act), round(act["rule_anomaly_label"].mean(), 3)]
    fp = pd.Series({"control rows (no injection) flagged by rules": f"{int(ctl['rule_anomaly_label'].sum())}/{len(ctl)}",
                    "pre/post-fault normal rows flagged": f"{int(pre['rule_anomaly_label'].sum())}/{len(pre)}"})
    thr = pd.DataFrame(params["channels"]).T[["target", "scale", "quant_step", "soft", "hard", "n_fit"]]
    cls_obs = enh["fault_type"].value_counts()
    md = f"""# Labeling report - M100 node 1 (ExaData) labeled datasets

> **All labels are proxies.** The source telemetry contains NO verified failure, maintenance, failure-onset or RUL information.
> `anomaly_label`/`fault_type` are *heuristic rule outputs* on observed data. `synthetic_*` columns are *ground truth only inside an explicit simulation*. Nothing here is a confirmed equipment fault.

## 1. Time coverage, sampling and gaps
- Rows: **{len(df)}**; span **{ts.min()} -> {ts.max()}** (wall-clock 3.4 days, but only ~{(df.shape[0] * 20 / 3600):.1f} h of sampled data because of gaps).
- Duplicate timestamps: {val['duplicate_timestamps']}; chronologically ordered: {val['chronological_order']}.
- Segments (gap > {L.GAP_SECONDS:.0f} s starts a new segment, same rule as `feature_engineering_1.py`):

{_md(segs)}

- Gaps > 60 s:

{_md(big)}

- Distribution of row-to-row intervals (s): note 407 intervals of 40 s = one missed sample. They are kept inside a segment (time-based gap rule), whereas `predictive_maintenance.py` (`1.5 x median = 30 s`) would split the series at each of them (~410 segments). Both are defensible; this report follows `feature_engineering_1.py`.

{_md(intervals)}

## 2. Missing values
Original telemetry columns contain **no missing values** (only `gap_seconds` is blank on row 0). Label columns:

{_md(miss)}

{_md(lab_miss)}

## 3. Labeling method (observed data)
Rules use only the current and past rows of the same segment (verified by a prefix-truncation test). For each family, channels compare each sample with a *normal-behaviour reference fitted on the train split only* (robust Huber regression on causal load/ambient features; monotone small tree for fan speed), standardised by max(MAD, sensor resolution):

{_md(thr)}

- **thermal**: P0/P1 temperature higher than expected for current CPU power (EWMA 3 and 8 samples) and ambient; P0-P1 temperature gradient.
- **fan_performance**: mean fan speed deviating from the monotone temperature/load reference (both directions) or fan0/fan1 mismatch.
- **power**: ps0+ps1 input power inconsistent with CPU power; ps0/ps1 imbalance.
- `hard` = max(train 99.5th percentile of |z|, 4); `soft` = max(98th percentile, 3). Hard exceedance on **3 consecutive samples** -> anomaly. Soft-only or non-persistent evidence -> `ambiguous_unknown` (blank anomaly_label). First {L.WARMUP} rows of each segment -> `insufficient_context`.
- Excluded channel: P0-P1 CPU power balance. It is stable in train but shifts in val/test (p0-p1 offset changes with workload mix), so it labeled workload regime change, not faults.

## 4. Class counts (observed)
fault_type x split:

{_md(cls)}

Percent within split:

{_md(clsp)}

anomaly_label x split (blank = ambiguous/insufficient):

{_md(anom)}

**Imbalance:** anomalies are {100 * (enh['anomaly_label'] == 1).mean():.2f}% of all rows ({int((enh['anomaly_label'] == 1).sum())}); `power_anomaly` has {int(cls_obs.get('power_anomaly', 0))} rows and `combined_anomaly` {int(cls_obs.get('combined_anomaly', 0))} - too few and too concentrated in few events for reliable multiclass learning. Train anomalies are almost absent while test holds most, i.e. distribution shift between days.

`anomaly_within_next_{H}` (future target) x split:

{_md(fut)}

Onset subset (rows whose current anomaly_label==0):

{_md(fut_on)}

## 5. Synthetic dataset
{len(syn)} rows in {syn['scenario_id'].nunique()} scenarios (180 samples each) copied from observed windows that contain no heuristic anomalies. Scenarios per kind/split:

{_md(syn_cnt)}

Rows per `synthetic_fault_type`:

{_md(syn_rows)}

Rows per `synthetic_severity_stage`:

{_md(syn_stage)}

### Rule-vs-injection agreement (how many injected faults the heuristic rules would flag; rows with a valid rule label only)
{_md(agree)}

{_md(fp.to_frame('flagged'))}

Low recall for subtle injections is expected and informative: the rules have conservative thresholds, so weak/early injections are intentionally below detectability. Synthetic labels therefore represent injected truth, not rule output.

Simulation assumptions (all parameters in `labeling_params.json`):
""" + "\n".join(f"- **{k}**: {v}" for k, v in params["simulation"]["assumptions"].items()) + f"""

## 6. Validation results
```json
{json.dumps(val, indent=2)}
```

## 7. Assumptions and limitations
1. **No ground truth.** Heuristic labels reproduce a rule, not a failure. A model that scores well on them has learned the rule (see `model_results.md` leakage ablation).
2. **Only {len(df) * 20 / 3600:.1f} h of data over 3.4 days, 4 segments, a few load episodes.** Rare classes are single episodes; metrics on them are anecdotal.
3. **Non-stationarity.** Fan idle baseline, ambient and the p0-p1 power offset differ between early and late data; train-fitted references are applied to later data, which is intended (chronological protocol) but means test labels include some regime shift.
4. **Undocumented units** for every metric (units above are presumptions). No manufacturer thresholds were used or assumed; thresholds come from data quantiles with sensor-resolution floors.
5. **Power family is nearly unsupported** in the observed data (the ps~CPU-power relation is lumpy; train hard threshold is wide).
6. **Simulation couplings** (fan->temperature 20 C per unit deficit at full load, p1 = 0.8 x p0 offset, 10-40 % PSU input drift) are assumptions, not measured physics. Synthetic fan speeds can fall below the observed idle floor.
7. **No RUL / failure time** is provided or inferable. `synthetic_severity_stage` is an injected-intensity indicator and `anomaly_within_next_{H}` is a heuristic-event horizon; neither is degradation to failure.
8. After a fault recovers, the thermal-inertia lag can leave a +/-1 C residual tail (observed in 19 temperature values) while `synthetic_label` is already 0: a known boundary-label imprecision.
9. Synthetic scenarios reuse observed base windows; scenarios from the same split share base data (overlap only within a split, never across).
"""
    (out / "labeling_report.md").write_text(md)
    stats = {"class_counts": cls_obs.to_dict(), "synthetic_rule_agreement": agree.to_dict()}
    (out / "labeling_stats.json").write_text(json.dumps(stats, indent=2, default=str))
    return stats
