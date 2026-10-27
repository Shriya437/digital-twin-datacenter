"""Train/evaluate an SVM classifier for multiclass or binary anomaly classification. Run from repository root or this folder."""
import argparse, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score, accuracy_score, average_precision_score
from classification_common import load_task, get_splits, best_f1_threshold, compute_multiclass_metrics, resolve_data_dir, SEED

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data/m100_labeling/outputs/labeled_dataset')
    ap.add_argument('--dataset', choices=['synthetic', 'observed'], default='synthetic')
    ap.add_argument('--task', choices=['multiclass', 'binary'], default='multiclass')
    ap.add_argument('--output-dir', default='outputs/classification_experiments')
    ap.add_argument('--c', type=float, default=1.0)
    ap.add_argument('--kernel', choices=['rbf', 'linear', 'poly'], default='rbf')
    args = ap.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    X, y, split = load_task(data_dir, args.dataset, task=args.task)
    tr, va, te = get_splits(split)

    model = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('model', SVC(C=args.c, kernel=args.kernel, class_weight='balanced', probability=True, random_state=SEED))
    ])
    model.fit(X.iloc[tr], y.iloc[tr])

    if args.task == 'multiclass':
        classes = list(model.named_steps['model'].classes_)
        labels = sorted(list(set(y.iloc[tr]) | set(y.iloc[te])))
        pred = model.predict(X.iloc[te])
        proba = model.predict_proba(X.iloc[te])
        yt = y.iloc[te].to_numpy()

        metrics = compute_multiclass_metrics(yt, pred, labels=labels)
        report = {
            'model': f'SVM_{args.kernel.upper()}',
            'dataset': args.dataset,
            'task': args.task,
            'c': args.c,
            'kernel': args.kernel,
            'n_train': len(tr),
            'n_val': len(va),
            'n_test': len(te),
            'classes_in_train': sorted(set(y.iloc[tr])),
            'classes_in_test': sorted(set(yt)),
            **metrics
        }

        stem = f'svm_{args.dataset}_multiclass'
        joblib.dump({'model': model, 'feature_columns': list(X.columns), 'labels': labels, 'classes': classes, 'dataset': args.dataset, 'task': args.task}, out / f'{stem}.joblib')

        pred_df = pd.DataFrame({'y_true': yt, 'y_pred': pred, 'model': f'SVM_{args.kernel.upper()}', 'dataset': args.dataset, 'task': args.task})
        for idx, cls_name in enumerate(classes):
            pred_df[f'prob_{cls_name}'] = proba[:, idx]
        pred_df.to_csv(out / f'{stem}_test_predictions.csv', index=False)

        metrics_file = out / f'{stem}_metrics.json'
        metrics_file.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        print('Saved model:', out / f'{stem}.joblib')
        print('Saved predictions:', out / f'{stem}_test_predictions.csv')
        print('Saved metrics:', metrics_file)
    else:
        pv = model.predict_proba(X.iloc[va])[:, 1]
        threshold = best_f1_threshold(y.iloc[va], pv)
        p = model.predict_proba(X.iloc[te])[:, 1]
        pred = (p >= threshold).astype(int)
        yt = y.iloc[te].to_numpy()
        report = {
            'model': f'SVM_{args.kernel.upper()}',
            'dataset': args.dataset,
            'task': args.task,
            'threshold_from_validation': threshold,
            'n_test': len(te),
            'positives_test': int(yt.sum()),
            'accuracy': float(accuracy_score(yt, pred)),
            'precision': float(precision_score(yt, pred, zero_division=0)),
            'recall': float(recall_score(yt, pred, zero_division=0)),
            'f1': float(f1_score(yt, pred, zero_division=0)),
            'pr_auc': float(average_precision_score(yt, p)) if yt.sum() else None,
            'confusion_matrix_labels_0_1': confusion_matrix(yt, pred, labels=[0, 1]).tolist(),
            'classification_report': classification_report(yt, pred, labels=[0, 1], target_names=['normal', 'anomaly'], output_dict=True, zero_division=0)
        }
        stem = f'svm_{args.dataset}'
        joblib.dump({'model': model, 'feature_columns': list(X.columns), 'threshold': threshold, 'dataset': args.dataset, 'task': args.task}, out / f'{stem}.joblib')
        pd.DataFrame({'y_true': yt, 'y_pred': pred, 'probability_anomaly': p, 'model': f'SVM_{args.kernel.upper()}', 'dataset': args.dataset}).to_csv(out / f'{stem}_test_predictions.csv', index=False)
        (out / f'{stem}_metrics.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
