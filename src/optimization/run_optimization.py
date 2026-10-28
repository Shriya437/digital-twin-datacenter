"""CLI for Bayesian optimization with automatic before/after comparison."""
import argparse
import json
from pathlib import Path
import pandas as pd

from src.optimization.model_spaces import ALL_MODELS
from src.optimization.bayesian_optimizer import run_optimization


def main():
    parser = argparse.ArgumentParser(description="Bayesian optimization and baseline comparison for data-center ML models.")
    parser.add_argument("--model", choices=sorted(ALL_MODELS) + ["all"], default="all")
    parser.add_argument("--task", choices=["auto", "regression", "classification", "anomaly"], default="auto")
    parser.add_argument("--trials", type=int, default=30, help="Optuna trials per model (more trials take longer).")
    parser.add_argument("--target", default="p0_vdd_temp", help="Regression target telemetry metric.")
    parser.add_argument("--horizon", type=int, default=45, help="Forecast horizon in rows; default is 45.")
    parser.add_argument("--dataset", choices=["synthetic", "observed"], default="synthetic",
                        help="Classification dataset. Synthetic labels are injected scenario labels; observed labels are heuristic proxies.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="optimization_results")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    models = sorted(ALL_MODELS) if args.model == "all" else [args.model]
    comparisons = []
    for name in models:
        result = run_optimization(
            model_name=name, task=args.task, n_trials=args.trials,
            target=args.target, horizon=args.horizon, dataset=args.dataset,
            seed=args.seed, output_dir=out,
        )
        c = result["before_after_comparison"]
        row = {
            "model": c["model"],
            "task": c["task"],
            "primary_metric": c["primary_metric"],
            "baseline_score": c["baseline_primary_score"],
            "optimized_score": c["optimized_primary_score"],
            "improvement_absolute": c["improvement_absolute"],
            "improvement_percent_of_baseline": c["improvement_percent_of_baseline"],
            "improved": c["improved"],
        }
        for metric, values in c["metrics"].items():
            row[f"{metric}_before"] = values.get("before")
            row[f"{metric}_after"] = values.get("after")
            row[f"{metric}_change_after_minus_before"] = values.get("change_after_minus_before", values.get("change"))
        comparisons.append(row)

    comparison_path = out / "before_after_comparison.csv"
    pd.DataFrame(comparisons).to_csv(comparison_path, index=False)
    print("\n\n================ ALL MODELS: BEFORE vs AFTER ================")
    print(pd.DataFrame(comparisons).to_string(index=False))
    print(f"\nCombined comparison saved to: {comparison_path.resolve()}")


if __name__ == "__main__":
    main()
