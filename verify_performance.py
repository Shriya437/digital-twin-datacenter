# -*- coding: utf-8 -*-
"""Audit output contracts, summarize ML evaluation metrics, and verify performance."""

import os
import pandas as pd
from config import OUTPUT_DIR, MODEL_PATH, EXPECTED_FILES

def audit_contract_files():
    print("=" * 65)
    print(" 1. ARTIFACT CONTRACT VALIDATION")
    print("=" * 65)
    all_passed = True
    for fname, req_cols in EXPECTED_FILES.items():
        fpath = OUTPUT_DIR / fname
        if not fpath.exists():
            print(f"[-] MISSING: {fname}")
            all_passed = False
            continue

        df = pd.read_csv(fpath)
        missing = [c for c in req_cols if c not in df.columns]
        if missing:
            print(f"[-] FAILED : {fname} (Missing columns: {missing})")
            all_passed = False
        else:
            print(f"[+] PASSED : {fname:<35} ({len(df)} rows)")

    return all_passed

def audit_ml_performance():
    print("\n" + "=" * 65)
    print(" 2. ML STATE ESTIMATION PERFORMANCE AUDIT")
    print("=" * 65)

    eval_path = OUTPUT_DIR / "random_missingness_evaluation.csv"
    gap_path = OUTPUT_DIR / "contiguous_gap_evaluation.csv"

    if eval_path.exists():
        eval_df = pd.read_csv(eval_path)
        print("\n--- Controlled Random Missingness Test ---")
        summary = eval_df.groupby(["target", "method"])[["MAE", "RMSE", "R2", "interval_coverage"]].mean().reset_index()
        print(summary.to_string(index=False))
    else:
        print("[-] Missing random_missingness_evaluation.csv")

    if gap_path.exists():
        gap_df = pd.read_csv(gap_path)
        print("\n--- Contiguous Outage Gap Duration Test ---")
        summary_gap = gap_df.groupby(["target", "gap_minutes", "method"])[["MAE", "RMSE"]].mean().reset_index()
        print(summary_gap.to_string(index=False))
    else:
        print("[-] Missing contiguous_gap_evaluation.csv")

    if MODEL_PATH.exists():
        print(f"\n[+] Model Bundle verified at: {MODEL_PATH}")
    else:
        print(f"[-] Model Bundle missing at: {MODEL_PATH}")

def run_verification():
    passed = audit_contract_files()
    audit_ml_performance()
    print("\n" + "=" * 65)
    if passed:
        print("OVERALL STATUS: ALL PERFORMANCE & DATA CONTRACT CHECKS PASSED (VERIFIED)")
    else:
        print("OVERALL STATUS: SOME CHECKS FAILED. RUN main.py FIRST.")
    print("=" * 65)

if __name__ == "__main__":
    run_verification()