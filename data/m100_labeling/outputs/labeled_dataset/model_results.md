# Baseline model results (chronological splits; all labels are heuristic proxies or simulation truth)

Protocol: train rows -> fit; val rows -> threshold (max-F1) and isotonic calibration; test rows -> report. 30-row purge at split cuts. Features are past-only within a segment/scenario. Positive classes are tiny (see `positives`), so every number has wide uncertainty; treat as sanity checks, not performance claims.


## T1_observed_anomaly_label__causal_features

| model                         |   n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier |   brier_isotonic | CM [[TN,FP],[FN,TP]]   |
|:------------------------------|----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|-----------------:|:-----------------------|
| MajorityClass                 | 877 |          62 |      0.5    |       0     |    0     | 0     |    0.071 |  0.0696 |         nan      | [[815, 0], [62, 0]]    |
| NaiveThreshold(temp_max>42.0) | 877 |          62 |      0.5    |       0.353 |    0.484 | 0.408 |    0.207 |  0.0992 |         nan      | [[760, 55], [32, 30]]  |
| RandomForest                  | 877 |          62 |      0.1856 |       0.072 |    0.081 | 0.076 |    0.206 |  0.0684 |           0.0651 | [[751, 64], [57, 5]]   |
| HistGB                        | 877 |          62 |      0.027  |       0.102 |    0.081 | 0.09  |    0.239 |  0.1029 |           0.0665 | [[771, 44], [57, 5]]   |

## T1b_observed_anomaly_label__WITH_rule_evidence_LEAKAGE_CHECK

| model                         |   n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier |   brier_isotonic | CM [[TN,FP],[FN,TP]]   |
|:------------------------------|----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|-----------------:|:-----------------------|
| MajorityClass                 | 877 |          62 |      0.5    |       0     |    0     | 0     |    0.071 |  0.0696 |         nan      | [[815, 0], [62, 0]]    |
| NaiveThreshold(temp_max>42.0) | 877 |          62 |      0.5    |       0.353 |    0.484 | 0.408 |    0.207 |  0.0992 |         nan      | [[760, 55], [32, 30]]  |
| RandomForest                  | 877 |          62 |      0.5493 |       1     |    0.21  | 0.347 |    0.902 |  0.0273 |           0.0146 | [[815, 0], [49, 13]]   |
| HistGB                        | 877 |          62 |      1      |       1     |    0.597 | 0.747 |    0.908 |  0.0092 |           0.0091 | [[815, 0], [25, 37]]   |

## T1_INVALID_random_row_split_illustration

**random row split of overlapping 20 s windows; neighbouring rows leak across train/test. Shown only to quantify inflation. Do NOT cite.**

| model   |    n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier | brier_isotonic   | CM [[TN,FP],[FN,TP]]   |
|:--------|-----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|:-----------------|:-----------------------|
| HistGB  | 1353 |          31 |         0.5 |       0.969 |        1 | 0.984 |    0.996 |  0.0009 |                  | [[1321, 1], [0, 31]]   |

## T2_observed_future_anomaly_next15_onset_subset

| model                         |   n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier |   brier_isotonic | CM [[TN,FP],[FN,TP]]   |
|:------------------------------|----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|-----------------:|:-----------------------|
| MajorityClass                 | 682 |          13 |       0.5   |       0     |        0 | 0     |    0.019 |  0.0187 |         nan      | [[669, 0], [13, 0]]    |
| NaiveThreshold(temp_max>42.0) | 682 |          13 |       0.5   |       0.591 |        1 | 0.743 |    0.591 |  0.0132 |         nan      | [[660, 9], [0, 13]]    |
| RandomForest                  | 682 |          13 |       0.003 |       0.058 |        1 | 0.11  |    0.061 |  0.0426 |           0.0184 | [[459, 210], [0, 13]]  |
| HistGB                        | 682 |          13 |       0     |       0.03  |        1 | 0.059 |    0.092 |  0.0526 |           0.0185 | [[252, 417], [0, 13]]  |

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
|                         |   precision |   recall |   f1-score |   support |
|:------------------------|------------:|---------:|-----------:|----------:|
| combined_anomaly        |       0     |    0     |      0     |        43 |
| fan_performance_anomaly |       0.182 |    0.2   |      0.19  |        10 |
| normal                  |       0.931 |    0.989 |      0.959 |       815 |
| power_anomaly           |       0     |    0     |      0     |         0 |
| thermal_anomaly         |       0     |    0     |      0     |         9 |
**HistGB** macro-F1 (classes present in test): 0.282; train classes ['fan_performance_anomaly', 'normal', 'power_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[0, 0, 43, 0, 0]
[0, 3, 7, 0, 0]
[0, 21, 791, 3, 0]
[0, 0, 0, 0, 0]
[0, 0, 9, 0, 0]
```
|                         |   precision |   recall |   f1-score |   support |
|:------------------------|------------:|---------:|-----------:|----------:|
| combined_anomaly        |       0     |    0     |      0     |        43 |
| fan_performance_anomaly |       0.125 |    0.3   |      0.176 |        10 |
| normal                  |       0.931 |    0.971 |      0.95  |       815 |
| power_anomaly           |       0     |    0     |      0     |         0 |
| thermal_anomaly         |       0     |    0     |      0     |         9 |

## S1_synthetic_label__binary

| model                         |    n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier |   brier_isotonic | CM [[TN,FP],[FN,TP]]      |
|:------------------------------|-----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|-----------------:|:--------------------------|
| MajorityClass                 | 3320 |        1496 |      0.5    |       0     |    0     | 0     |    0.451 |  0.2486 |         nan      | [[1824, 0], [1496, 0]]    |
| NaiveThreshold(temp_max>43.0) | 3320 |        1496 |      0.5    |       0.489 |    0.045 | 0.082 |    0.452 |  0.4515 |         nan      | [[1754, 70], [1429, 67]]  |
| RandomForest                  | 3320 |        1496 |      0.7156 |       0.929 |    0.757 | 0.834 |    0.949 |  0.0926 |           0.0947 | [[1737, 87], [363, 1133]] |
| HistGB                        | 3320 |        1496 |      0.8903 |       0.936 |    0.805 | 0.865 |    0.954 |  0.0673 |           0.0866 | [[1741, 83], [292, 1204]] |

## S2_synthetic_future_anomaly_next15_onset_subset

| model                         |    n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier |   brier_isotonic | CM [[TN,FP],[FN,TP]]     |
|:------------------------------|-----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|-----------------:|:-------------------------|
| MajorityClass                 | 1657 |         240 |      0.5    |       0     |    0     | 0     |    0.145 |  0.1239 |         nan      | [[1417, 0], [240, 0]]    |
| NaiveThreshold(temp_max>42.0) | 1657 |         240 |      0.5    |       0.403 |    0.129 | 0.196 |    0.178 |  0.1539 |         nan      | [[1371, 46], [209, 31]]  |
| RandomForest                  | 1657 |         240 |      0.2742 |       0.273 |    0.2   | 0.231 |    0.288 |  0.1193 |           0.1214 | [[1289, 128], [192, 48]] |
| HistGB                        | 1657 |         240 |      0.2205 |       0.189 |    0.221 | 0.204 |    0.188 |  0.1348 |           0.1258 | [[1190, 227], [187, 53]] |

## S3_synthetic_fault_type_multiclass

**RandomForest** macro-F1 (classes present in test): 0.797; train classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[165, 59, 8, 3, 28]
[6, 471, 41, 0, 30]
[21, 7, 1691, 2, 103]
[3, 0, 76, 122, 6]
[3, 0, 79, 0, 396]
```
|                         |   precision |   recall |   f1-score |   support |
|:------------------------|------------:|---------:|-----------:|----------:|
| combined_anomaly        |       0.833 |    0.627 |      0.716 |       263 |
| fan_performance_anomaly |       0.877 |    0.859 |      0.868 |       548 |
| normal                  |       0.892 |    0.927 |      0.909 |      1824 |
| power_anomaly           |       0.961 |    0.589 |      0.731 |       207 |
| thermal_anomaly         |       0.703 |    0.828 |      0.761 |       478 |
**HistGB** macro-F1 (classes present in test): 0.759; train classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']; test classes ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
```
labels: ['combined_anomaly', 'fan_performance_anomaly', 'normal', 'power_anomaly', 'thermal_anomaly']
[115, 58, 11, 9, 70]
[30, 474, 35, 0, 9]
[33, 7, 1701, 4, 79]
[23, 0, 57, 124, 3]
[2, 0, 61, 0, 415]
```
|                         |   precision |   recall |   f1-score |   support |
|:------------------------|------------:|---------:|-----------:|----------:|
| combined_anomaly        |       0.567 |    0.437 |      0.494 |       263 |
| fan_performance_anomaly |       0.879 |    0.865 |      0.872 |       548 |
| normal                  |       0.912 |    0.933 |      0.922 |      1824 |
| power_anomaly           |       0.905 |    0.599 |      0.721 |       207 |
| thermal_anomaly         |       0.72  |    0.868 |      0.787 |       478 |

## X1_cross_domain_synthetic_to_observed_heuristic

| model                                    |   n |   positives |   threshold |   precision |   recall |    f1 |   pr_auc |   brier | brier_isotonic   | CM [[TN,FP],[FN,TP]]   |
|:-----------------------------------------|----:|------------:|------------:|------------:|---------:|------:|---------:|--------:|:-----------------|:-----------------------|
| HistGB(synthetic-train -> observed-test) | 877 |          62 |      0.8903 |       0.457 |    0.597 | 0.517 |    0.499 |  0.0797 |                  | [[771, 44], [25, 37]]  |