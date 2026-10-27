"""Create/save confusion matrix and classification metrics from a test-predictions CSV."""
import argparse, json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report, precision_score, recall_score, f1_score, accuracy_score

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--predictions',required=True,help='CSV with y_true and y_pred columns, created by a training script'); ap.add_argument('--output-dir',default='outputs/classification_experiments'); args=ap.parse_args()
    src=Path(args.predictions); out=Path(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(src)
    if not {'y_true','y_pred'}.issubset(df.columns): raise ValueError('CSV must contain y_true and y_pred columns')
    yt=df.y_true.astype(int); yp=df.y_pred.astype(int); cm=confusion_matrix(yt,yp,labels=[0,1])
    name=src.stem.replace('_test_predictions','')
    metrics={'source_predictions':str(src),'labels_order':[0,1],'label_names':['normal','anomaly'],'confusion_matrix_TN_FP_FN_TP':cm.tolist(),'accuracy':accuracy_score(yt,yp),'precision':precision_score(yt,yp,zero_division=0),'recall':recall_score(yt,yp,zero_division=0),'f1':f1_score(yt,yp,zero_division=0),'classification_report':classification_report(yt,yp,labels=[0,1],target_names=['normal','anomaly'],output_dict=True,zero_division=0)}
    (out/f'{name}_evaluation.json').write_text(json.dumps(metrics,indent=2))
    disp=ConfusionMatrixDisplay(confusion_matrix=cm,display_labels=['Normal (0)','Anomaly (1)']); disp.plot(values_format='d'); plt.title(f'Confusion Matrix — {name}'); plt.tight_layout(); plt.savefig(out/f'{name}_confusion_matrix.png',dpi=180); plt.close()
    print(json.dumps(metrics,indent=2)); print('Saved:',out/f'{name}_evaluation.json'); print('Saved:',out/f'{name}_confusion_matrix.png')
if __name__=='__main__': main()
