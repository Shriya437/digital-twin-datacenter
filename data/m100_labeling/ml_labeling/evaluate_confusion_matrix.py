"""Create/save confusion matrix and classification metrics from a test-predictions CSV (binary or multiclass)."""
import argparse, json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import (
    confusion_matrix, ConfusionMatrixDisplay, classification_report,
    precision_score, recall_score, f1_score, accuracy_score
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--predictions', required=True, help='CSV with y_true and y_pred columns, created by a training script')
    ap.add_argument('--output-dir', default='outputs/classification_experiments')
    args = ap.parse_args()

    src = Path(args.predictions)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(src)
    if not {'y_true', 'y_pred'}.issubset(df.columns):
        raise ValueError('CSV must contain y_true and y_pred columns')

    name = src.stem.replace('_test_predictions', '')

    # Check whether the task is binary (0/1) or multiclass
    raw_true = df['y_true']
    raw_pred = df['y_pred']

    is_binary = False
    try:
        int_true = raw_true.astype(int)
        int_pred = raw_pred.astype(int)
        unique_vals = set(int_true.unique()) | set(int_pred.unique())
        if unique_vals.issubset({0, 1}):
            is_binary = True
    except (ValueError, TypeError):
        is_binary = False

    if is_binary:
        yt = int_true
        yp = int_pred
        cm = confusion_matrix(yt, yp, labels=[0, 1])
        metrics = {
            'source_predictions': str(src),
            'task': 'binary',
            'labels_order': [0, 1],
            'label_names': ['normal', 'anomaly'],
            'confusion_matrix_TN_FP_FN_TP': cm.tolist(),
            'accuracy': float(accuracy_score(yt, yp)),
            'precision': float(precision_score(yt, yp, zero_division=0)),
            'recall': float(recall_score(yt, yp, zero_division=0)),
            'f1': float(f1_score(yt, yp, zero_division=0)),
            'classification_report': classification_report(
                yt, yp, labels=[0, 1], target_names=['normal', 'anomaly'], output_dict=True, zero_division=0
            )
        }
        fig, ax = plt.subplots(figsize=(6, 5))
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=['Normal (0)', 'Anomaly (1)'])
        disp.plot(ax=ax, values_format='d', cmap='Blues')
        plt.title(f'Confusion Matrix — {name}')
        plt.tight_layout()
        plt.savefig(out / f'{name}_confusion_matrix.png', dpi=180)
        plt.close()
    else:
        yt = raw_true.astype(str)
        yp = raw_pred.astype(str)
        labels = sorted(list(set(yt.unique()) | set(yp.unique())))
        cm = confusion_matrix(yt, yp, labels=labels)
        rep = classification_report(yt, yp, labels=labels, output_dict=True, zero_division=0)
        metrics = {
            'source_predictions': str(src),
            'task': 'multiclass',
            'labels_order': labels,
            'confusion_matrix': cm.tolist(),
            'accuracy': float(accuracy_score(yt, yp)),
            'macro_precision': float(precision_score(yt, yp, labels=labels, average='macro', zero_division=0)),
            'macro_recall': float(recall_score(yt, yp, labels=labels, average='macro', zero_division=0)),
            'macro_f1': float(f1_score(yt, yp, labels=labels, average='macro', zero_division=0)),
            'weighted_f1': float(f1_score(yt, yp, labels=labels, average='weighted', zero_division=0)),
            'per_class': {c: {k: round(v, 4) if isinstance(v, float) else v for k, v in rep[c].items()} for c in labels if c in rep},
            'classification_report': rep
        }
        fig, ax = plt.subplots(figsize=(8, 6.5))
        disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=labels)
        disp.plot(ax=ax, values_format='d', cmap='Blues', colorbar=True)
        plt.title(f'Multiclass Confusion Matrix — {name}', fontsize=12, pad=12)
        plt.xticks(rotation=25, ha='right', fontsize=9)
        plt.yticks(fontsize=9)
        plt.tight_layout()
        plt.savefig(out / f'{name}_confusion_matrix.png', dpi=180)
        plt.close()

    eval_file = out / f'{name}_evaluation.json'
    eval_file.write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))
    print('Saved evaluation:', eval_file)
    print('Saved confusion matrix plot:', out / f'{name}_confusion_matrix.png')

if __name__ == '__main__':
    main()
