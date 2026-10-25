# Labeling report - M100 node 1 (ExaData) labeled datasets

> **All labels are proxies.** The source telemetry contains NO verified failure, maintenance, failure-onset or RUL information.
> `anomaly_label`/`fault_type` are *heuristic rule outputs* on observed data. `synthetic_*` columns are *ground truth only inside an explicit simulation*. Nothing here is a confirmed equipment fault.

## 1. Time coverage, sampling and gaps
- Rows: **4917**; span **2020-04-01 07:20:00+00:00 -> 2020-04-04 16:52:40+00:00** (wall-clock 3.4 days, but only ~27.3 h of sampled data because of gaps).
- Duplicate timestamps: 0; chronologically ordered: True.
- Segments (gap > 60 s starts a new segment, same rule as `feature_engineering_1.py`):

|   seg | start                     | end                       |   rows |   duration_min |   usable_labeled_rows |
|------:|:--------------------------|:--------------------------|-------:|---------------:|----------------------:|
|     1 | 2020-04-01 07:20:00+00:00 | 2020-04-01 13:29:40+00:00 |   1110 |          369.7 |                  1096 |
|     2 | 2020-04-03 16:58:00+00:00 | 2020-04-03 17:02:40+00:00 |     15 |            4.7 |                     1 |
|     3 | 2020-04-03 17:05:40+00:00 | 2020-04-04 15:53:20+00:00 |   3705 |         1367.7 |                  3415 |
|     4 | 2020-04-04 16:21:20+00:00 | 2020-04-04 16:52:40+00:00 |     87 |           31.3 |                    57 |

- Gaps > 60 s:

|      |   row_id | timestamp                 |   gap_seconds_before_row |
|-----:|---------:|:--------------------------|-------------------------:|
| 1110 |     1110 | 2020-04-03 16:58:00+00:00 |                   185300 |
| 1125 |     1125 | 2020-04-03 17:05:40+00:00 |                      180 |
| 4830 |     4830 | 2020-04-04 16:21:20+00:00 |                     1680 |

- Distribution of row-to-row intervals (s): note 407 intervals of 40 s = one missed sample. They are kept inside a segment (time-based gap rule), whereas `predictive_maintenance.py` (`1.5 x median = 30 s`) would split the series at each of them (~410 segments). Both are defensible; this report follows `feature_engineering_1.py`.

|   interval_seconds |   rows |
|-------------------:|-------:|
|                 20 |   4506 |
|                 40 |    407 |
|                180 |      1 |
|               1680 |      1 |
|             185300 |      1 |

## 2. Missing values
Original telemetry columns contain **no missing values** (only `gap_seconds` is blank on row 0). Label columns:

|                 |   missing_in_file |   pct |
|:----------------|------------------:|------:|
| timestamp       |                 0 |  0    |
| ambient         |                 0 |  0    |
| p0_vdd_temp     |                 0 |  0    |
| p1_vdd_temp     |                 0 |  0    |
| fan0_0          |                 0 |  0    |
| fan1_0          |                 0 |  0    |
| p0_power        |                 0 |  0    |
| p1_power        |                 0 |  0    |
| ps0_input_power |                 0 |  0    |
| ps1_input_power |                 0 |  0    |
| total_power     |                 0 |  0    |
| gap_seconds     |                 1 |  0.02 |

|                        |   blank_or_NA |
|:-----------------------|--------------:|
| anomaly_label          |           348 |
| fault_type             |             0 |
| anomaly_within_next_15 |           856 |

## 3. Labeling method (observed data)
Rules use only the current and past rows of the same segment (verified by a prefix-truncation test). For each family, channels compare each sample with a *normal-behaviour reference fitted on the train split only* (robust Huber regression on causal load/ambient features; monotone small tree for fan speed), standardised by max(MAD, sensor resolution):

|                 | target             |   scale |   quant_step |    soft |    hard |   n_fit |
|:----------------|:-------------------|--------:|-------------:|--------:|--------:|--------:|
| z_temp_p0       | p0_vdd_temp        |  1      |       1      |  3      |  4      |    2908 |
| z_temp_p1       | p1_vdd_temp        |  1      |       1      |  3      |  4      |    2908 |
| z_temp_gradient | temp_gradient      |  1      |       1      |  3      |  4      |    2908 |
| z_fan_level     | fan_mean           | 71.3716 |      50      | 24.5314 | 28.7348 |    2908 |
| z_fan_mismatch  | fan_mismatch_ratio |  0.0227 |       0.0227 |  3      |  4      |    2908 |
| z_ps_total      | ps_input_sum       | 14.826  |      10      | 42.8644 | 45.2399 |    2908 |
| z_ps_balance    | ps_balance         | 14.6088 |      10      |  9.0247 | 20.3491 |    2908 |

- **thermal**: P0/P1 temperature higher than expected for current CPU power (EWMA 3 and 8 samples) and ambient; P0-P1 temperature gradient.
- **fan_performance**: mean fan speed deviating from the monotone temperature/load reference (both directions) or fan0/fan1 mismatch.
- **power**: ps0+ps1 input power inconsistent with CPU power; ps0/ps1 imbalance.
- `hard` = max(train 99.5th percentile of |z|, 4); `soft` = max(98th percentile, 3). Hard exceedance on **3 consecutive samples** -> anomaly. Soft-only or non-persistent evidence -> `ambiguous_unknown` (blank anomaly_label). First 14 rows of each segment -> `insufficient_context`.
- Excluded channel: P0-P1 CPU power balance. It is stable in train but shifts in val/test (p0-p1 offset changes with workload mix), so it labeled workload regime change, not faults.

## 4. Class counts (observed)
fault_type x split:

| fault_type              |   purge |   test |   train |   val |   All |
|:------------------------|--------:|-------:|--------:|------:|------:|
| ambiguous_unknown       |       1 |     63 |     155 |    73 |   292 |
| combined_anomaly        |       0 |     43 |       0 |     0 |    43 |
| fan_performance_anomaly |       2 |     10 |      19 |     4 |    35 |
| insufficient_context    |       0 |     14 |      42 |     0 |    56 |
| normal                  |      57 |    815 |    2730 |   863 |  4465 |
| power_anomaly           |       0 |      0 |       4 |     0 |     4 |
| thermal_anomaly         |       0 |      9 |       0 |    13 |    22 |
| All                     |      60 |    954 |    2950 |   953 |  4917 |

Percent within split:

| fault_type              |   purge |   test |   train |   val |
|:------------------------|--------:|-------:|--------:|------:|
| ambiguous_unknown       |    1.67 |   6.6  |    5.25 |  7.66 |
| combined_anomaly        |    0    |   4.51 |    0    |  0    |
| fan_performance_anomaly |    3.33 |   1.05 |    0.64 |  0.42 |
| insufficient_context    |    0    |   1.47 |    1.42 |  0    |
| normal                  |   95    |  85.43 |   92.54 | 90.56 |
| power_anomaly           |    0    |   0    |    0.14 |  0    |
| thermal_anomaly         |    0    |   0.94 |    0    |  1.36 |

anomaly_label x split (blank = ambiguous/insufficient):

| anomaly_label   |   purge |   test |   train |   val |   All |
|:----------------|--------:|-------:|--------:|------:|------:|
| 0               |      57 |    815 |    2730 |   863 |  4465 |
| 1               |       2 |     62 |      23 |    17 |   104 |
| blank           |       1 |     77 |     197 |    73 |   348 |
| All             |      60 |    954 |    2950 |   953 |  4917 |

**Imbalance:** anomalies are 2.28% of all rows (104); `power_anomaly` has 4 rows and `combined_anomaly` 43 - too few and too concentrated in few events for reliable multiclass learning. Train anomalies are almost absent while test holds most, i.e. distribution shift between days.

`anomaly_within_next_15` (future target) x split:

| anomaly_within_next_15   |   purge |   test |   train |   val |   All |
|:-------------------------|--------:|-------:|--------:|------:|------:|
| 0                        |      58 |    677 |    2316 |   772 |  3823 |
| 1                        |       1 |    100 |      91 |    46 |   238 |
| blank                    |       1 |    177 |     543 |   135 |   856 |
| All                      |      60 |    954 |    2950 |   953 |  4917 |

Onset subset (rows whose current anomaly_label==0):

| anomaly_within_next_15   |   purge |   test |   train |   val |
|:-------------------------|--------:|-------:|--------:|------:|
| 0                        |      57 |    669 |    2304 |   767 |
| 1                        |       0 |     13 |      44 |    13 |
| blank                    |       0 |    133 |     382 |    83 |

## 5. Synthetic dataset
16200 rows in 90 scenarios (180 samples each) copied from observed windows that contain no heuristic anomalies. Scenarios per kind/split:

| injected_fault_type     |   test |   train |   val |   All |
|:------------------------|-------:|--------:|------:|------:|
| combined_anomaly        |      4 |      10 |     4 |    18 |
| fan_performance_anomaly |      4 |      10 |     4 |    18 |
| none                    |      4 |      10 |     4 |    18 |
| power_anomaly           |      4 |      10 |     4 |    18 |
| thermal_anomaly         |      4 |      10 |     4 |    18 |
| All                     |     20 |      50 |    20 |    90 |

Rows per `synthetic_fault_type`:

| synthetic_fault_type    |   test |   train |   val |   All |
|:------------------------|-------:|--------:|------:|------:|
| combined_anomaly        |    263 |     833 |   159 |  1255 |
| fan_performance_anomaly |    548 |    1145 |   551 |  2244 |
| normal                  |   2104 |    4986 |  2153 |  9243 |
| power_anomaly           |    207 |     698 |   222 |  1127 |
| thermal_anomaly         |    478 |    1338 |   515 |  2331 |
| All                     |   3600 |    9000 |  3600 | 16200 |

Rows per `synthetic_severity_stage`:

| synthetic_severity_stage   |   test |   train |   val |   All |
|:---------------------------|-------:|--------:|------:|------:|
| 0                          |   2104 |    4986 |  2153 |  9243 |
| 1                          |    225 |     463 |   179 |   867 |
| 2                          |    364 |     655 |   232 |  1251 |
| 3                          |    907 |    2896 |  1036 |  4839 |
| All                        |   3600 |    9000 |  3600 | 16200 |

### Rule-vs-injection agreement (how many injected faults the heuristic rules would flag; rows with a valid rule label only)
| synthetic_fault_type    |   rows |   rule_recall |
|:------------------------|-------:|--------------:|
| combined_anomaly        |   1025 |         0.736 |
| fan_performance_anomaly |   2117 |         0.419 |
| power_anomaly           |   1046 |         0.025 |
| thermal_anomaly         |   1973 |         0.818 |
| ALL injected-active     |   6161 |         0.532 |

|                                              | flagged   |
|:---------------------------------------------|:----------|
| control rows (no injection) flagged by rules | 0/2888    |
| pre/post-fault normal rows flagged           | 0/4797    |

Low recall for subtle injections is expected and informative: the rules have conservative thresholds, so weak/early injections are intentionally below detectability. Synthetic labels therefore represent injected truth, not rule output.

Simulation assumptions (all parameters in `labeling_params.json`):
- **thermal**: p0 temp offset A=k*hard_threshold_C, k~U(0.75,2.5); p1 gets 0.8*A (shared cooling, p0/p1 corr 0.99 in data); offset passes a first-order lag (EWMA span 6) to mimic thermal inertia; rounded to 1 C (sensor resolution).
- **fan**: fan speed multiplied by (1 - m*d), d~U(0.10,0.30); either fan0 only or both fans (50/50); rounded to 100 (sensor resolution). Synthetic fan speed may fall below the observed idle floor (4200) because a degraded fan is by definition out-of-envelope.
- **fan_thermal_coupling**: ASSUMPTION (not verified): reduced airflow raises both processor temperatures by 20 C * m*d * load_fraction (load_fraction in [0,1] from causal CPU-power EWMA); same thermal lag.
- **power**: ps0_input_power multiplied by (1 + m*a), a~U(0.10,0.40), p0/p1 power untouched (input power not explained by CPU power); total_power shifted by the same absolute delta times the data-derived slope of total_power on ps0+ps1 (=0.9344); rounded to 10 (resolution).
- **profiles**: gradual (linear ramp 30-70 samples, p=0.7) or abrupt (3-sample ramp, p=0.3); hold; recovery with p=0.5 (20-40 samples) else persists to window end; power 'spike' variant uses abrupt ramp, hold 8-20, recovery 3.
- **combined**: two distinct components out of {thermal, fan, power}, onsets differ by 0-20 samples.
- **labels**: synthetic_label = 1 iff injected intensity m >= 0.20; severity stage 0:<0.2, 1:0.2-0.5, 2:0.5-0.9, 3:>=0.9 (abrupt faults jump to 3). Stage is injected-effect intensity, NOT time-to-failure or RUL.

## 6. Validation results
```json
{
  "row_count_equal": true,
  "original_columns_identical": true,
  "original_timestamp_strings_identical": true,
  "duplicate_timestamps": 0,
  "chronological_order": true,
  "missing_values_in_original_telemetry": 0,
  "n_segments": 4,
  "rows_following_gap_gt_60s": 3,
  "labels_never_cross_gap": true,
  "allowed_fault_types_only": true,
  "anomaly_label_values": [
    0,
    1
  ],
  "anomaly1_iff_class_in_anomaly_set": true,
  "causal_labels_prefix_test_passed": true,
  "synthetic_rows": 16200,
  "synthetic_scenarios": 90,
  "synthetic_rows_without_scenario": 0,
  "synthetic_origin_values": [
    "synthetic"
  ],
  "observed_origin_values": [
    "observed"
  ],
  "synthetic_control_and_preonset_rows_differing_from_base": 0,
  "base_ts_matches_original": true,
  "synthetic_base_split_consistent": true,
  "base_rows_shared_across_splits": 0,
  "scenarios_with_single_split": true,
  "unique_scenario_timestamp_pairs": true,
  "observed_file_modified": false
}
```

## 7. Assumptions and limitations
1. **No ground truth.** Heuristic labels reproduce a rule, not a failure. A model that scores well on them has learned the rule (see `model_results.md` leakage ablation).
2. **Only 27.3 h of data over 3.4 days, 4 segments, a few load episodes.** Rare classes are single episodes; metrics on them are anecdotal.
3. **Non-stationarity.** Fan idle baseline, ambient and the p0-p1 power offset differ between early and late data; train-fitted references are applied to later data, which is intended (chronological protocol) but means test labels include some regime shift.
4. **Undocumented units** for every metric (units above are presumptions). No manufacturer thresholds were used or assumed; thresholds come from data quantiles with sensor-resolution floors.
5. **Power family is nearly unsupported** in the observed data (the ps~CPU-power relation is lumpy; train hard threshold is wide).
6. **Simulation couplings** (fan->temperature 20 C per unit deficit at full load, p1 = 0.8 x p0 offset, 10-40 % PSU input drift) are assumptions, not measured physics. Synthetic fan speeds can fall below the observed idle floor.
7. **No RUL / failure time** is provided or inferable. `synthetic_severity_stage` is an injected-intensity indicator and `anomaly_within_next_15` is a heuristic-event horizon; neither is degradation to failure.
8. After a fault recovers, the thermal-inertia lag can leave a +/-1 C residual tail (observed in 19 temperature values) while `synthetic_label` is already 0: a known boundary-label imprecision.
9. Synthetic scenarios reuse observed base windows; scenarios from the same split share base data (overlap only within a split, never across).
