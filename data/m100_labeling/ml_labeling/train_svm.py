"""Train/evaluate an SVM classifier. Run from repository root or this folder."""
import argparse, json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score, average_precision_score
from classification_common import load_task, get_splits, best_f1_threshold, SEED

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data-dir', default='data/m100_labeling/outputs/labeled_dataset'); ap.add_argument('--dataset', choices=['synthetic','observed'], default='synthetic'); ap.add_argument('--output-dir', default='outputs/classification_experiments'); args=ap.parse_args()
    data_dir=Path(args.data_dir); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    X,y,split=load_task(data_dir,args.dataset); tr,va,te=get_splits(split)
    model=Pipeline([('imputer',SimpleImputer(strategy='median')),('scaler',StandardScaler()),('model',SVC(C=1.0,kernel='rbf',class_weight='balanced',probability=True,random_state=SEED))])
    model.fit(X.iloc[tr],y.iloc[tr]); pv=model.predict_proba(X.iloc[va])[:,1]; threshold=best_f1_threshold(y.iloc[va],pv); p=model.predict_proba(X.iloc[te])[:,1]; pred=(p>=threshold).astype(int); yt=y.iloc[te].to_numpy()
    report={'model':'SVM_RBF','dataset':args.dataset,'threshold_from_validation':threshold,'n_test':len(te),'positives_test':int(yt.sum()),'precision':precision_score(yt,pred,zero_division=0),'recall':recall_score(yt,pred,zero_division=0),'f1':f1_score(yt,pred,zero_division=0),'pr_auc':average_precision_score(yt,p) if yt.sum() else None,'confusion_matrix_labels_0_1':confusion_matrix(yt,pred,labels=[0,1]).tolist(),'classification_report':classification_report(yt,pred,labels=[0,1],target_names=['normal','anomaly'],output_dict=True,zero_division=0)}
    joblib.dump({'model':model,'feature_columns':list(X.columns),'threshold':threshold,'dataset':args.dataset},out/f'svm_{args.dataset}.joblib')
    pd.DataFrame({'y_true':yt,'y_pred':pred,'probability_anomaly':p,'model':'SVM_RBF','dataset':args.dataset}).to_csv(out/f'svm_{args.dataset}_test_predictions.csv',index=False)
    (out/f'svm_{args.dataset}_metrics.json').write_text(json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
