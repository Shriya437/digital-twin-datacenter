"""Train RF, HistGB, SVM, KNN and evaluate their soft-voting ensemble."""
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
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score, average_precision_score
from classification_common import load_task, get_splits, best_f1_threshold, SEED

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data-dir',default='data/m100_labeling/outputs/labeled_dataset'); ap.add_argument('--dataset',choices=['synthetic','observed'],default='synthetic'); ap.add_argument('--output-dir',default='outputs/classification_experiments'); ap.add_argument('--neighbors',type=int,default=7); args=ap.parse_args()
    data_dir=Path(args.data_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    X,y,split=load_task(data_dir,args.dataset); tr,va,te=get_splits(split)
    if args.neighbors < 1 or args.neighbors > len(tr): raise ValueError('neighbors must be between 1 and number of training rows')
    models={
      'RandomForest':Pipeline([('imputer',SimpleImputer(strategy='median')),('model',RandomForestClassifier(n_estimators=300,min_samples_leaf=3,class_weight='balanced_subsample',n_jobs=-1,random_state=SEED))]),
      'HistGradientBoosting':Pipeline([('imputer',SimpleImputer(strategy='median')),('model',HistGradientBoostingClassifier(max_depth=4,learning_rate=0.06,max_iter=250,class_weight='balanced',random_state=SEED))]),
      'SVM_RBF':Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler()),('model',SVC(C=1.0,kernel='rbf',class_weight='balanced',probability=True,random_state=SEED))]),
      'KNN':Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler()),('model',KNeighborsClassifier(n_neighbors=args.neighbors,weights='distance'))])}
    for m in models.values(): m.fit(X.iloc[tr],y.iloc[tr])
    # Select threshold from validation probabilities only. Soft voting = mean predicted probability.
    val_prob=np.mean([m.predict_proba(X.iloc[va])[:,1] for m in models.values()],axis=0)
    threshold=best_f1_threshold(y.iloc[va],val_prob)
    test_prob=np.mean([m.predict_proba(X.iloc[te])[:,1] for m in models.values()],axis=0); pred=(test_prob>=threshold).astype(int); yt=y.iloc[te].to_numpy()
    report={'model':'SoftVoting_RF_HistGB_SVM_KNN','members':list(models),'dataset':args.dataset,'threshold_from_validation':threshold,'n_test':len(te),'positives_test':int(yt.sum()),'precision':precision_score(yt,pred,zero_division=0),'recall':recall_score(yt,pred,zero_division=0),'f1':f1_score(yt,pred,zero_division=0),'pr_auc':average_precision_score(yt,test_prob) if yt.sum() else None,'confusion_matrix_labels_0_1':confusion_matrix(yt,pred,labels=[0,1]).tolist(),'classification_report':classification_report(yt,pred,labels=[0,1],target_names=['normal','anomaly'],output_dict=True,zero_division=0)}
    joblib.dump({'models':models,'feature_columns':list(X.columns),'threshold':threshold,'dataset':args.dataset,'ensemble':'unweighted_soft_voting'},out/f'ensemble_four_{args.dataset}.joblib')
    pd.DataFrame({'y_true':yt,'y_pred':pred,'probability_anomaly':test_prob,'model':'SoftVoting_RF_HistGB_SVM_KNN','dataset':args.dataset}).to_csv(out/f'ensemble_four_{args.dataset}_test_predictions.csv',index=False)
    (out/f'ensemble_four_{args.dataset}_metrics.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
