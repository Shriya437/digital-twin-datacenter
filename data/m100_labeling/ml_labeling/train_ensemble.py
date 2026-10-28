"""Train RF, HistGB, SVM, KNN and evaluate their soft-voting ensemble for multiclass or binary classification."""
import argparse, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score, accuracy_score, average_precision_score
from classification_common import load_task, get_splits, best_f1_threshold, compute_multiclass_metrics, resolve_data_dir, SEED

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default='data/m100_labeling/outputs/labeled_dataset')
    ap.add_argument('--dataset', choices=['synthetic', 'observed'], default='synthetic')
    ap.add_argument('--task', choices=['multiclass', 'binary'], default='multiclass')
    ap.add_argument('--output-dir', default='outputs/classification_experiments')
    ap.add_argument('--neighbors', type=int, default=7)
    args = ap.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    X, y, split = load_task(data_dir, args.dataset, task=args.task)
    tr, va, te = get_splits(split)
    if args.neighbors < 1 or args.neighbors > len(tr):
        raise ValueError('neighbors must be between 1 and number of training rows')

    models = {
        'RandomForest': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight='balanced_subsample', n_jobs=-1, random_state=SEED))
        ]),
        'HistGradientBoosting': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('model', HistGradientBoostingClassifier(max_depth=4, learning_rate=0.06, max_iter=250, class_weight='balanced', random_state=SEED))
        ]),
        'SVM_RBF': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
            ('model', SVC(C=1.0, kernel='rbf', class_weight='balanced', probability=True, random_state=SEED))
        ]),
        'KNN': Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
            ('model', KNeighborsClassifier(n_neighbors=args.neighbors, weights='distance'))
        ])
    }

    print('Fitting ensemble members on training set...')
    for name, m in models.items():
        print(f' - Training {name}...')
        m.fit(X.iloc[tr], y.iloc[tr])

    if args.task == 'multiclass':
        classes = list(models['RandomForest'].named_steps['model'].classes_)
        labels = sorted(list(set(y.iloc[tr]) | set(y.iloc[te])))
        yt = y.iloc[te].to_numpy()

        member_metrics = {}
        model_probs = []
        for name, m in models.items():
            mp = m.predict_proba(X.iloc[te])
            model_probs.append(mp)
            m_pred = np.array(classes)[np.argmax(mp, axis=1)]
            m_metrics = compute_multiclass_metrics(yt, m_pred, labels=labels)
            member_metrics[name] = {
                'accuracy': m_metrics['accuracy'],
                'macro_f1': m_metrics['macro_f1'],
                'weighted_f1': m_metrics['weighted_f1'],
            }

        ensemble_prob = np.mean(model_probs, axis=0)
        pred_idx = np.argmax(ensemble_prob, axis=1)
        pred = np.array(classes)[pred_idx]

        metrics = compute_multiclass_metrics(yt, pred, labels=labels)
        report = {
            'model': 'SoftVoting_RF_HistGB_SVM_KNN',
            'dataset': args.dataset,
            'task': args.task,
            'members': list(models.keys()),
            'member_performances': member_metrics,
            'n_train': len(tr),
            'n_val': len(va),
            'n_test': len(te),
            'classes_in_train': sorted(set(y.iloc[tr])),
            'classes_in_test': sorted(set(yt)),
            **metrics
        }

        stem = f'ensemble_four_{args.dataset}_multiclass'
        joblib.dump({
            'models': models,
            'feature_columns': list(X.columns),
            'labels': labels,
            'classes': classes,
            'dataset': args.dataset,
            'task': args.task,
            'ensemble': 'unweighted_soft_voting'
        }, out / f'{stem}.joblib')

        pred_df = pd.DataFrame({'y_true': yt, 'y_pred': pred, 'model': 'SoftVoting_RF_HistGB_SVM_KNN', 'dataset': args.dataset, 'task': args.task})
        for idx, cls_name in enumerate(classes):
            pred_df[f'prob_{cls_name}'] = ensemble_prob[:, idx]
        pred_df.to_csv(out / f'{stem}_test_predictions.csv', index=False)

        metrics_file = out / f'{stem}_metrics.json'
        metrics_file.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        print('Saved model:', out / f'{stem}.joblib')
        print('Saved predictions:', out / f'{stem}_test_predictions.csv')
        print('Saved metrics:', metrics_file)
    else:
        val_prob = np.mean([m.predict_proba(X.iloc[va])[:, 1] for m in models.values()], axis=0)
        threshold = best_f1_threshold(y.iloc[va], val_prob)
        test_prob = np.mean([m.predict_proba(X.iloc[te])[:, 1] for m in models.values()], axis=0)
        pred = (test_prob >= threshold).astype(int)
        yt = y.iloc[te].to_numpy()
        report = {
            'model': 'SoftVoting_RF_HistGB_SVM_KNN',
            'members': list(models.keys()),
            'dataset': args.dataset,
            'task': args.task,
            'threshold_from_validation': threshold,
            'n_test': len(te),
            'positives_test': int(yt.sum()),
            'accuracy': float(accuracy_score(yt, pred)),
            'precision': float(precision_score(yt, pred, zero_division=0)),
            'recall': float(recall_score(yt, pred, zero_division=0)),
            'f1': float(f1_score(yt, pred, zero_division=0)),
            'pr_auc': float(average_precision_score(yt, test_prob)) if yt.sum() else None,
            'confusion_matrix_labels_0_1': confusion_matrix(yt, pred, labels=[0, 1]).tolist(),
            'classification_report': classification_report(yt, pred, labels=[0, 1], target_names=['normal', 'anomaly'], output_dict=True, zero_division=0)
        }
        stem = f'ensemble_four_{args.dataset}'
        joblib.dump({
            'models': models,
            'feature_columns': list(X.columns),
            'threshold': threshold,
            'dataset': args.dataset,
            'task': args.task,
            'ensemble': 'unweighted_soft_voting'
        }, out / f'{stem}.joblib')
        pd.DataFrame({'y_true': yt, 'y_pred': pred, 'probability_anomaly': test_prob, 'model': 'SoftVoting_RF_HistGB_SVM_KNN', 'dataset': args.dataset}).to_csv(out / f'{stem}_test_predictions.csv', index=False)
        (out / f'{stem}_metrics.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
