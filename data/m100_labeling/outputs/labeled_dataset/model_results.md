# Baseline model results (chronological splits; all labels are heuristic proxies or simulation truth)

Protocol: train rows -> fit; val rows -> threshold (max-F1) and isotonic calibration; test rows -> report. 30-row purge at split cuts. Features are past-only within a segment/scenario. Positive classes are tiny (see `positives`), so every number has wide uncertainty; treat as sanity checks, not performance claims.


## T1_observed_anomaly_label__causal_features

```
                        model   n  positives  threshold  precision  recall    f1  pr_auc  brier  brier_isotonic  CM [[TN,FP],[FN,TP]]
                MajorityClass 877         62     0.5000      0.000   0.000 0.000   0.071 0.0696             NaN   [[815, 0], [62, 0]]
NaiveThreshold(temp_max>42.0) 877         62     0.5000      0.353   0.484 0.408   0.207 0.0992             NaN [[760, 55], [32, 30]]
                 RandomForest 877         62     0.1821      0.068   0.081 0.074   0.206 0.0688          0.0651  [[747, 68], [57, 5]]
                       HistGB 877         62     0.0025      0.147   0.161 0.154   0.229 0.1039          0.0659 [[757, 58], [52, 10]]
```

## T1b_observed_anomaly_label__WITH_rule_evidence_LEAKAGE_CHECK

```
                        model   n  positives  threshold  precision  recall    f1  pr_auc  brier  brier_isotonic  CM [[TN,FP],[FN,TP]]
                MajorityClass 877         62      0.500      0.000   0.000 0.000   0.071 0.0696             NaN   [[815, 0], [62, 0]]
NaiveThreshold(temp_max>42.0) 877         62      0.500      0.353   0.484 0.408   0.207 0.0992             NaN [[760, 55], [32, 30]]
                 RandomForest 877         62      0.536      1.000   0.242 0.390   0.901 0.0278          0.0147  [[815, 0], [47, 15]]
                       HistGB 877         62      1.000      1.000   0.790 0.883   0.908 0.0092          0.0091  [[815, 0], [13, 49]]
```

## T1_INVALID_random_row_split_illustration

**random row split of overlapping 20 s windows; neighbouring rows leak across train/test. Shown only to quantify inflation. Do NOT cite.**

```
 model    n  positives  threshold  precision  recall    f1  pr_auc  brier brier_isotonic CM [[TN,FP],[FN,TP]]
HistGB 1353         31        0.5      0.939     1.0 0.969   0.996 0.0012           None [[1320, 2], [0, 31]]
```

## T2_observed_future_anomaly_next15_onset_subset

```
                        model   n  positives  threshold  precision  recall    f1  pr_auc  brier  brier_isotonic  CM [[TN,FP],[FN,TP]]
                MajorityClass 682         13     0.5000      0.000     0.0 0.000   0.019 0.0187             NaN   [[669, 0], [13, 0]]
NaiveThreshold(temp_max>42.0) 682         13     0.5000      0.591     1.0 0.743   0.591 0.0132             NaN   [[660, 9], [0, 13]]
                 RandomForest 682         13     0.0033      0.075     1.0 0.139   0.060 0.0424          0.0183 [[508, 161], [0, 13]]
                       HistGB 682         13     0.0000      0.024     1.0 0.046   0.088 0.0529          0.0186 [[134, 535], [0, 13]]
```

## T3_observed_fault_type_multiclass

**RandomForest** macro-F1 (classes present in test): 0.287; train classes ['fan_performance_anomaly', 'normal', 'power_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[0, 0, 43, 0, 0]
[0, 2, 8, 0, 0]
[0, 9, 806, 0, 0]
[0, 0, 0, 0, 0]
[0, 0, 9, 0, 0]
```
```
                         precision  recall  f1-score  support
combined_anomaly             0.000   0.000     0.000     43.0
fan_performance_anomaly      0.182   0.200     0.190     10.0
normal                       0.931   0.989     0.959    815.0
power_anomaly                0.000   0.000     0.000      0.0
thermal_anomaly              0.000   0.000     0.000      9.0
```
**HistGB** macro-F1 (classes present in test): 0.283; train classes ['fan_performance_anomaly', 'normal', 'power_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[0, 0, 43, 0, 0]
[0, 3, 7, 0, 0]
[0, 20, 790, 5, 0]
[0, 0, 0, 0, 0]
[0, 0, 8, 1, 0]
```
```
                         precision  recall  f1-score  support
combined_anomaly             0.000   0.000     0.000     43.0
fan_performance_anomaly      0.130   0.300     0.182     10.0
normal                       0.932   0.969     0.950    815.0
power_anomaly                0.000   0.000     0.000      0.0
thermal_anomaly              0.000   0.000     0.000      9.0
```

## S1_synthetic_label__binary

```
                        model    n  positives  threshold  precision  recall    f1  pr_auc  brier  brier_isotonic      CM [[TN,FP],[FN,TP]]
                MajorityClass 3320       1496     0.5000      0.000   0.000 0.000   0.451 0.2486             NaN    [[1824, 0], [1496, 0]]
NaiveThreshold(temp_max>43.0) 3320       1496     0.5000      0.489   0.045 0.082   0.452 0.4515             NaN  [[1754, 70], [1429, 67]]
                 RandomForest 3320       1496     0.7215      0.938   0.750 0.834   0.953 0.0905          0.0909 [[1750, 74], [374, 1122]]
                       HistGB 3320       1496     0.8790      0.943   0.822 0.878   0.961 0.0650          0.0792 [[1749, 75], [266, 1230]]
```

## S2_synthetic_future_anomaly_next15_onset_subset

```
                        model    n  positives  threshold  precision  recall    f1  pr_auc  brier  brier_isotonic     CM [[TN,FP],[FN,TP]]
                MajorityClass 1657        240     0.5000      0.000   0.000 0.000   0.145 0.1239             NaN    [[1417, 0], [240, 0]]
NaiveThreshold(temp_max>42.0) 1657        240     0.5000      0.403   0.129 0.196   0.178 0.1539             NaN  [[1371, 46], [209, 31]]
                 RandomForest 1657        240     0.2967      0.358   0.163 0.223   0.297 0.1197          0.1220  [[1347, 70], [201, 39]]
                       HistGB 1657        240     0.2148      0.208   0.263 0.232   0.190 0.1357          0.1259 [[1177, 240], [177, 63]]
```

## S3_synthetic_fault_type_multiclass

**RandomForest** macro-F1 (classes present in test): 0.794; train classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[161, 61, 8, 5, 28]
[7, 473, 37, 0, 31]
[20, 8, 1693, 2, 101]
[2, 0, 81, 123, 1]
[4, 0, 82, 0, 392]
```
```
                         precision  recall  f1-score  support
combined_anomaly             0.830   0.612     0.705    263.0
fan_performance_anomaly      0.873   0.863     0.868    548.0
normal                       0.891   0.928     0.909   1824.0
power_anomaly                0.946   0.594     0.730    207.0
thermal_anomaly              0.709   0.820     0.760    478.0
```
**HistGB** macro-F1 (classes present in test): 0.759; train classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[113, 58, 13, 6, 73]
[30, 474, 30, 0, 14]
[33, 9, 1696, 4, 82]
[27, 0, 49, 125, 6]
[1, 0, 57, 0, 420]
```
```
                         precision  recall  f1-score  support
combined_anomaly             0.554   0.430     0.484    263.0
fan_performance_anomaly      0.876   0.865     0.871    548.0
normal                       0.919   0.930     0.925   1824.0
power_anomaly                0.926   0.604     0.731    207.0
thermal_anomaly              0.706   0.879     0.783    478.0
```

## X1_cross_domain_synthetic_to_observed_heuristic

```
                                   model   n  positives  threshold  precision  recall    f1  pr_auc  brier brier_isotonic  CM [[TN,FP],[FN,TP]]
HistGB(synthetic-train -> observed-test) 877         62      0.879      0.487   0.597 0.536   0.561 0.0804           None [[776, 39], [25, 37]]
```