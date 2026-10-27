"""Run multiclass anomaly classification for KNN, SVM, and Ensemble, then evaluate confusion matrices and save comparison metrics."""
import argparse, json, subprocess, sys
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent

def to_markdown_table(df):
    """Render a GitHub-flavored Markdown table from a DataFrame without external dependencies."""
    headers = list(df.columns)
    lines = ["| " + " | ".join(str(h) for h in headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines)

def run_cmd(cmd, desc):
    print(f"\n=======================================================")
    print(f"--> {desc}")
    print(f"Command: {' '.join(cmd)}")
    print(f"=======================================================\n")
    res = subprocess.run(cmd, cwd=str(HERE.parent.parent.parent), capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.returncode != 0:
        print(f"ERROR: {res.stderr}", file=sys.stderr)
        raise RuntimeError(f"Command failed with code {res.returncode}: {' '.join(cmd)}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data/m100_labeling/outputs/labeled_dataset')
    ap.add_argument('--dataset', choices=['synthetic', 'observed'], default='synthetic')
    ap.add_argument('--output-dir', default='outputs/classification_experiments')
    ap.add_argument('--neighbors', type=int, default=7)
    ap.add_argument('--skip-training', action='store_true', help='Skip training and regenerate evaluation/comparison summary from existing prediction files')
    args = ap.parse_args()

    python_exe = sys.executable
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not args.skip_training:
        # 1. Train KNN
        run_cmd([
            python_exe, str(HERE / "train_knn.py"),
            "--data-dir", args.data_dir,
            "--dataset", args.dataset,
            "--task", "multiclass",
            "--output-dir", args.output_dir,
            "--neighbors", str(args.neighbors)
        ], "Training Multiclass KNN Classifier")

        # 2. Train SVM
        run_cmd([
            python_exe, str(HERE / "train_svm.py"),
            "--data-dir", args.data_dir,
            "--dataset", args.dataset,
            "--task", "multiclass",
            "--output-dir", args.output_dir
        ], "Training Multiclass SVM Classifier")

        # 3. Train Ensemble
        run_cmd([
            python_exe, str(HERE / "train_ensemble.py"),
            "--data-dir", args.data_dir,
            "--dataset", args.dataset,
            "--task", "multiclass",
            "--output-dir", args.output_dir,
            "--neighbors", str(args.neighbors)
        ], "Training Multiclass Four-Model Ensemble")

    # 4. Generate confusion matrices and evaluation reports
    pred_files = [
        out / f"knn_{args.dataset}_multiclass_test_predictions.csv",
        out / f"svm_{args.dataset}_multiclass_test_predictions.csv",
        out / f"ensemble_four_{args.dataset}_multiclass_test_predictions.csv"
    ]

    for pf in pred_files:
        if pf.exists():
            run_cmd([
                python_exe, str(HERE / "evaluate_confusion_matrix.py"),
                "--predictions", str(pf),
                "--output-dir", args.output_dir
            ], f"Evaluating Confusion Matrix for {pf.name}")

    # 5. Build consolidated comparison metrics file
    models_summary = []
    comparison = {
        "dataset": args.dataset,
        "task": "multiclass",
        "models": {}
    }

    metrics_files = {
        "KNN": out / f"knn_{args.dataset}_multiclass_metrics.json",
        "SVM": out / f"svm_{args.dataset}_multiclass_metrics.json",
        "Ensemble (RF+HistGB+SVM+KNN)": out / f"ensemble_four_{args.dataset}_multiclass_metrics.json"
    }

    for name, mf in metrics_files.items():
        if mf.exists():
            data = json.loads(mf.read_text())
            comparison["models"][name] = data
            models_summary.append({
                "Model": name,
                "Accuracy": f"{data.get('accuracy', 0):.4f}",
                "Macro F1": f"{data.get('macro_f1', 0):.4f}",
                "Weighted F1": f"{data.get('weighted_f1', 0):.4f}",
                "Macro Precision": f"{data.get('macro_precision', 0):.4f}",
                "Macro Recall": f"{data.get('macro_recall', 0):.4f}",
            })

    # Save comparison JSON
    comp_json = out / f"multiclass_models_comparison.json"
    comp_json.write_text(json.dumps(comparison, indent=2))
    print(f"\nSaved consolidated comparison JSON: {comp_json}")

    # Save comparison Markdown
    df_summary = pd.DataFrame(models_summary)
    comp_md = out / f"multiclass_models_comparison.md"
    md_content = [
        f"# Multiclass Anomaly Classification - Model Comparison ({args.dataset.capitalize()} Dataset)\n",
        "## Overall Test Set Performance\n",
        to_markdown_table(df_summary),
        "\n\n## Per-Class F1 Scores\n"
    ]

    per_class_rows = []
    classes = []
    for name, data in comparison["models"].items():
        pc = data.get("per_class", {})
        if not classes:
            classes = sorted(pc.keys())
        row = {"Model": name}
        for c in classes:
            row[c] = f"{pc.get(c, {}).get('f1-score', 0):.4f}"
        per_class_rows.append(row)

    if per_class_rows:
        md_content.append(to_markdown_table(pd.DataFrame(per_class_rows)))

    comp_md.write_text("\n".join(md_content))
    print(f"Saved consolidated comparison Markdown: {comp_md}")
    print("\nMulticlass anomaly classification pipeline completed successfully!")

if __name__ == '__main__':
    main()
