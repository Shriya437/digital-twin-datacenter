"""Explicitly SIMULATED fault scenarios built from copies of observed telemetry windows.

Nothing here is real. Every synthetic row is traceable to (scenario_id, base_row_id).
All magnitudes are expressed relative to quantities estimated from the observed TRAIN
period; every assumption is recorded in SIM_ASSUMPTIONS and written to the params JSON.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from labeling import METRICS, WARMUP

WINDOW_LEN = 180        # samples per scenario (~60 min at 20 s)
STRIDE = 60             # candidate base-window stride (overlap only WITHIN one split)
ACTIVE_M = 0.20         # injected intensity >= this => synthetic_label = 1
KINDS = ["none", "thermal_anomaly", "fan_performance_anomaly", "power_anomaly", "combined_anomaly"]
N_PER_KIND = {"train": 10, "val": 4, "test": 4}

SIM_ASSUMPTIONS = {
    "thermal": "p0 temp offset A=k*hard_threshold_C, k~U(0.75,2.5); p1 gets 0.8*A (shared cooling, "
               "p0/p1 corr 0.99 in data); offset passes a first-order lag (EWMA span 6) to mimic thermal inertia; rounded to 1 C (sensor resolution).",
    "fan": "fan speed multiplied by (1 - m*d), d~U(0.10,0.30); either fan0 only or both fans (50/50); "
           "rounded to 100 (sensor resolution). Synthetic fan speed may fall below the observed idle floor (4200) because a degraded fan is by definition out-of-envelope.",
    "fan_thermal_coupling": "ASSUMPTION (not verified): reduced airflow raises both processor temperatures by 20 C * m*d * load_fraction (load_fraction in [0,1] from causal CPU-power EWMA); same thermal lag.",
    "power": "ps0_input_power multiplied by (1 + m*a), a~U(0.10,0.40), p0/p1 power untouched (input power not explained by CPU power); "
             "total_power shifted by the same absolute delta times the data-derived slope of total_power on ps0+ps1 (=%s); rounded to 10 (resolution).",
    "profiles": "gradual (linear ramp 30-70 samples, p=0.7) or abrupt (3-sample ramp, p=0.3); hold; recovery with p=0.5 (20-40 samples) else persists to window end; power 'spike' variant uses abrupt ramp, hold 8-20, recovery 3.",
    "combined": "two distinct components out of {thermal, fan, power}, onsets differ by 0-20 samples.",
    "labels": "synthetic_label = 1 iff injected intensity m >= 0.20; severity stage 0:<0.2, 1:0.2-0.5, 2:0.5-0.9, 3:>=0.9 (abrupt faults jump to 3). Stage is injected-effect intensity, NOT time-to-failure or RUL.",
}


def _profile(L, onset, ramp, hold, rec):
    m = np.zeros(L)
    r_end = min(onset + ramp, L)
    m[onset:r_end] = np.linspace(0, 1, ramp + 1)[1:][: r_end - onset]
    h_end = min(r_end + hold, L)
    m[r_end:h_end] = 1.0
    if rec > 0 and h_end < L:
        e = min(h_end + rec, L)
        m[h_end:e] = np.linspace(1, 0, rec + 1)[1:][: e - h_end]
    return m


def _draw_profile(rng, L, spike=False, onset_shift=0):
    onset = int(rng.integers(30, 71)) + onset_shift
    if spike:
        return _profile(L, onset, 2, int(rng.integers(8, 21)), 3), "abrupt"
    if rng.random() < 0.7:
        ramp, kind = int(rng.integers(30, 71)), "gradual"
    else:
        ramp, kind = 3, "abrupt"
    if rng.random() < 0.5:
        hold, rec = int(rng.integers(20, 51)), int(rng.integers(20, 41))
    else:
        hold, rec = L, 0
    return _profile(L, onset, ramp, hold, rec), kind


def _lag(x, span=6):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values


def candidate_windows(obs_split, seg, anomaly, pos):
    """(start,end) row-position windows fully inside one segment and one split, with no heuristic anomalies."""
    out = {"train": [], "val": [], "test": []}
    n = len(obs_split)
    for s in range(0, n - WINDOW_LEN + 1, STRIDE):
        e = s + WINDOW_LEN
        sp = set(obs_split[s:e])
        if len(sp) != 1 or list(sp)[0] not in out:
            continue
        if len(set(seg[s:e])) != 1:
            continue
        if (anomaly[s:e] == 1).any():
            continue
        out[list(sp)[0]].append((s, e))
    return out


def build_scenario(base: pd.DataFrame, kind: str, rng, params: dict, idle_cp: float, cp_range: float):
    """base: copy of observed window rows (original values). Returns (df_modified, meta, row_info)."""
    L = len(base)
    d = base[METRICS].astype(float).copy()
    cpe = (base["p0_power"] + base["p1_power"]).ewm(span=8, adjust=False).mean()
    loadfrac = np.clip((cpe - idle_cp) / max(cp_range, 1.0), 0, 1).values
    comps = {"thermal_anomaly": [], "fan_performance_anomaly": [], "power_anomaly": []}
    if kind == "none":
        chosen = []
    elif kind == "combined_anomaly":
        chosen = list(rng.choice(list(comps), size=2, replace=False))
    else:
        chosen = [kind]
    m_by, profile_kind, details = {}, {}, {}
    shift = 0
    temp_off0 = np.zeros(L); temp_off1 = np.zeros(L)
    for c in chosen:
        spike = (c == "power_anomaly" and rng.random() < 0.5)
        m, pk = _draw_profile(rng, L, spike=spike, onset_shift=shift)
        shift = int(rng.integers(0, 21))
        m_by[c], profile_kind[c] = m, ("spike" if spike else pk)
        if c == "thermal_anomaly":
            k = float(rng.uniform(0.75, 2.5)); A = k * params["thermal_hard_C"]
            off = _lag(m * A)
            temp_off0 += off; temp_off1 += 0.8 * off
            details[c] = {"k": round(k, 3), "amplitude_C": round(A, 2)}
        elif c == "fan_performance_anomaly":
            dd = float(rng.uniform(0.10, 0.30)); both = bool(rng.random() < 0.5)
            d["fan0_0"] = np.round(d["fan0_0"] * (1 - m * dd), -2)
            if both:
                d["fan1_0"] = np.round(d["fan1_0"] * (1 - m * dd), -2)
            off = _lag(20.0 * m * dd * loadfrac)
            temp_off0 += off; temp_off1 += off
            details[c] = {"deficit": round(dd, 3), "both_fans": both}
        else:
            a = float(rng.uniform(0.10, 0.40))
            delta = d["ps0_input_power"] * m * a
            d["ps0_input_power"] = np.round(d["ps0_input_power"] + delta, -1)
            d["total_power"] = np.round(d["total_power"] + params["total_vs_ps_slope"] * delta, -1)
            details[c] = {"rel_increase": round(a, 3)}
    d["p0_vdd_temp"] = np.round(d["p0_vdd_temp"] + temp_off0)
    d["p1_vdd_temp"] = np.round(d["p1_vdd_temp"] + temp_off1)
    for col in ["fan0_0", "fan1_0", "p0_vdd_temp", "p1_vdd_temp", "ps0_input_power", "ps1_input_power", "total_power"]:
        d[col] = d[col].astype(base[col].dtype)
    ms = np.vstack(list(m_by.values())) if m_by else np.zeros((1, L))
    active = ms >= ACTIVE_M
    n_act = active.sum(0)
    names = list(m_by)
    row_type = np.full(L, "normal", dtype=object)
    for i, c in enumerate(names):
        row_type[(n_act == 1) & active[i]] = c
    row_type[n_act >= 2] = "combined_anomaly"
    inten = ms.max(0)
    abrupt = all(v in ("abrupt", "spike") for v in profile_kind.values()) and bool(profile_kind)
    stage = np.where(inten < ACTIVE_M, 0, np.where(inten < 0.5, 1, np.where(inten < 0.9, 2, 3)))
    if abrupt:
        stage = np.where(inten >= ACTIVE_M, 3, 0)
    info = pd.DataFrame({"synthetic_label": (n_act >= 1).astype(int), "synthetic_fault_type": row_type,
                         "synthetic_severity_stage": stage, "injection_intensity": np.round(inten, 4)}, index=d.index)
    meta = {"injected_fault_type": kind, "injected_components": "+".join(names) if names else "none",
            "injection_profile": "+".join(f"{c}:{profile_kind[c]}" for c in names) if names else "none",
            "injection_params": str(details) if details else "none"}
    return d, meta, info
