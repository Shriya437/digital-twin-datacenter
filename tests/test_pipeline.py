"""Run from project root: python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from src.data_loader import METRICS
from src.asset_registry import build_asset_registry, build_metric_asset_mapping
from src.dependency_graph import build_dependency_graph, related_assets
from src.anomaly_detector import detect_anomalies
from src.root_cause import rank_root_causes
from src.feature_engineering import build_telemetry_features
from src.fault_scenarios import generate_scenarios
from src.evaluation import evaluate_scenarios
from src.graph_visualization import save_graph_plot
from src.impact_analysis import assess_potential_impact
from src.main import make_plot


def sample_df(n=160):
    rng = np.random.default_rng(123)
    timestamps = pd.date_range("2026-01-01", periods=n, freq="20s", tz="UTC")
    df = pd.DataFrame({"timestamp": timestamps})
    for i, metric in enumerate(METRICS):
        if metric.startswith("fan"):
            df[metric] = 4200 + rng.normal(0, 35, n)
        elif "temp" in metric or metric == "ambient":
            df[metric] = 30 + i + rng.normal(0, 0.4, n)
        else:
            df[metric] = 200 + i * 3 + rng.normal(0, 4, n)
    df["calculated_gap_flag"] = False
    df["calculated_gap_seconds"] = df["timestamp"].diff().dt.total_seconds()
    return df


class Member2PipelineTests(unittest.TestCase):
    def test_registry_graph_and_queries(self):
        df = sample_df(20)
        registry = build_asset_registry(df)
        graph = build_dependency_graph(registry)
        self.assertEqual(len(registry), len(METRICS) + 1)
        self.assertEqual(graph.number_of_nodes(), len(METRICS) + 1)
        self.assertEqual(graph.number_of_edges(), len(METRICS))
        self.assertEqual(len(build_metric_asset_mapping()), len(METRICS))
        self.assertIn("M100_NODE_1::p0_vdd_temp", related_assets(graph, "M100_NODE_1")["downstream"])
        with self.assertRaises(ValueError):
            related_assets(graph, "missing")

    def test_feature_engineering_resets_across_gap(self):
        df = sample_df(20)
        df.loc[10:, "timestamp"] += pd.Timedelta(hours=4)
        feat = build_telemetry_features(df, window=5, gap_threshold_seconds=60)
        self.assertIn("segment_id", feat.columns)
        self.assertGreater(feat.loc[10, "segment_id"], feat.loc[9, "segment_id"])
        self.assertTrue(pd.isna(feat.loc[10, "p0_vdd_temp_delta"]))

    def test_detectors_emit_expected_methods(self):
        df = sample_df(160)
        baseline = df.copy()
        df.loc[130, "p0_vdd_temp"] += 25
        events = detect_anomalies(df, baseline_df=baseline, contamination=0.02)
        self.assertTrue({"timestamp", "metric_name", "detector", "anomaly_score", "is_simulated"}.issubset(events.columns))
        self.assertTrue(set(events["detector"]).issubset({"robust_z_score", "rolling_robust_z_score", "isolation_forest", "pca_reconstruction"}))
        self.assertTrue((events["timestamp"] == df.loc[130, "timestamp"]).any())

    def test_root_cause_rank_has_abstention_and_evidence(self):
        df = sample_df(20)
        events = pd.DataFrame([{
            "timestamp": df.loc[10, "timestamp"], "metric_name": "p0_vdd_temp",
            "detector": "robust_z_score", "quality_warning": False, "is_simulated": False,
        }])
        result = rank_root_causes(df, events)
        self.assertFalse(result.empty)
        self.assertIn("candidate_cause", result.columns)
        self.assertIn("ranking_score", result.columns)

    def test_synthetic_scenarios_and_evaluation(self):
        df = sample_df(160)
        scenarios = generate_scenarios(df, start_fraction=0.72, duration=5)
        self.assertEqual(len(scenarios), 5)
        self.assertTrue(all(s.labels["is_simulated"].all() for s in scenarios))
        self.assertTrue(all(s.frame["injected_fault"].sum() == 5 for s in scenarios))
        det, labels, summary, cause_eval = evaluate_scenarios(df, scenarios[:1])
        self.assertFalse(summary.empty)
        self.assertTrue({"precision", "recall", "f1", "detection_delay_seconds"}.issubset(summary.columns))

    def test_plot_breaks_gap(self):
        df = sample_df(10)
        df.loc[5:, "timestamp"] += pd.Timedelta(minutes=20)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "plot.png"
            info = make_plot(df, pd.DataFrame(), p)
            self.assertTrue(p.exists())
            self.assertGreater(info["major_gaps_shown_on_plot"], 0)

    def test_graph_plot_and_impact(self):
        df = sample_df(20)
        graph = build_dependency_graph(build_asset_registry(df))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "graph.png"
            save_graph_plot(graph, p)
            self.assertTrue(p.exists())
        impact = assess_potential_impact(graph, "M100_NODE_1")
        self.assertEqual(len(impact), len(METRICS))
        self.assertTrue(impact["path_contains_unverified_physical_dependency"].all())

if __name__ == "__main__":
    unittest.main()
