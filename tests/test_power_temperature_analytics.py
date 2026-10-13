"""
Unit tests for Module 6: Power and Temperature Analytics
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.power_temperature_analytics import (
    load_telemetry,
    plot_power_metrics,
    plot_temperature_power,
    calculate_correlations,
    calculate_rolling_summaries,
    verify_power_unit,
    integrate_power_wh,
    run_what_if_analysis,
    prepare_forecasting_dataset,
    train_and_evaluate_temperature_forecast,
    predict_future_temperature,
)


def create_synthetic_telemetry(n=120, freq="20s"):
    rng = np.random.default_rng(42)
    timestamps = pd.date_range("2026-01-01 00:00:00", periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame({
        "timestamp": timestamps,
        "ambient": 22.0 + rng.normal(0, 0.5, n),
        "p0_vdd_temp": 32.0 + rng.normal(0, 1.5, n),
        "p1_vdd_temp": 31.0 + rng.normal(0, 1.5, n),
        "fan0_0": 4200.0 + rng.normal(0, 50, n),
        "fan1_0": 4300.0 + rng.normal(0, 50, n),
        "p0_power": 40.0 + rng.normal(0, 4, n),
        "p1_power": 35.0 + rng.normal(0, 4, n),
        "ps0_input_power": 260.0 + rng.normal(0, 10, n),
        "ps1_input_power": 270.0 + rng.normal(0, 10, n),
        "total_power": 450.0 + rng.normal(0, 20, n),
    })
    return df


class Module6AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)
        self.df = create_synthetic_telemetry(n=120)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_power_metrics_plotting_and_summary(self):
        plot_power_metrics(self.df, self.output_dir, max_gap_seconds=60)
        self.assertTrue((self.output_dir / "power_trends.png").exists())
        self.assertTrue((self.output_dir / "power_metrics_summary.csv").exists())
        summary_df = pd.read_csv(self.output_dir / "power_metrics_summary.csv")
        self.assertIn("metric", summary_df.columns)
        self.assertIn("mean", summary_df.columns)

    def test_temperature_power_comparison(self):
        plot_temperature_power(self.df, self.output_dir, max_gap_seconds=60)
        self.assertTrue((self.output_dir / "temperature_power_comparison.png").exists())
        self.assertTrue((self.output_dir / "power_temperature_relationship.png").exists())
        self.assertTrue((self.output_dir / "power_temperature_comparison.csv").exists())

    def test_correlation_analysis_spearman(self):
        calculate_correlations(self.df, self.output_dir)
        self.assertTrue((self.output_dir / "metric_correlations.csv").exists())
        self.assertTrue((self.output_dir / "metric_correlations_pearson.csv").exists())
        self.assertTrue((self.output_dir / "metric_correlation_counts.csv").exists())
        self.assertTrue((self.output_dir / "metric_correlation_matrix.png").exists())
        self.assertTrue((self.output_dir / "correlation_interpretation.csv").exists())
        interp = pd.read_csv(self.output_dir / "correlation_interpretation.csv")
        self.assertFalse(interp.empty)
        self.assertIn("spearman_rho", interp.columns)

    def test_rolling_summaries_respect_segment_boundaries(self):
        # Insert a 4-hour gap in the middle
        df_gap = self.df.copy()
        df_gap.loc[60:, "timestamp"] += pd.Timedelta(hours=4)

        calculate_rolling_summaries(df_gap, self.output_dir, max_gap_seconds=60, window=5, min_periods=3)
        self.assertTrue((self.output_dir / "rolling_telemetry_summary.csv").exists())
        self.assertTrue((self.output_dir / "rolling_telemetry_wide.csv").exists())
        self.assertTrue((self.output_dir / "rolling_statistics_summary.csv").exists())

        wide = pd.read_csv(self.output_dir / "rolling_telemetry_wide.csv")
        self.assertIn("_segment", wide.columns)
        self.assertGreater(wide.loc[60, "_segment"], wide.loc[59, "_segment"])

    def test_power_unit_verification(self):
        unit, factor, notes = verify_power_unit(self.df["total_power"], confirmed_unit="W")
        self.assertEqual(unit, "W")
        self.assertEqual(factor, 1.0)

        # Test auto detection of kW
        kw_series = self.df["total_power"] / 1000.0
        unit_kw, factor_kw, _ = verify_power_unit(kw_series, confirmed_unit="auto")
        self.assertEqual(unit_kw, "kW")
        self.assertEqual(factor_kw, 1000.0)

    def test_energy_integration_trapezoidal(self):
        df_gap = self.df.copy()
        # Introduce a gap at index 50
        df_gap.loc[50:, "timestamp"] += pd.Timedelta(hours=2)

        detailed_df, summary = integrate_power_wh(df_gap, power_column="total_power", confirmed_unit="W", max_gap_seconds=60)
        self.assertGreater(summary["integrated_total_Wh"], 0)
        self.assertGreater(summary["excluded_intervals"], 0)
        self.assertIn("valid_interval", detailed_df.columns)
        # Interval across the 2-hour gap must be invalid
        self.assertFalse(detailed_df.loc[50, "valid_interval"])

    def test_what_if_power_analysis(self):
        run_what_if_analysis(self.df, self.output_dir, power_column="total_power")
        self.assertTrue((self.output_dir / "what_if_power_comparison.csv").exists())
        self.assertTrue((self.output_dir / "what_if_power_comparison.png").exists())
        what_if_df = pd.read_csv(self.output_dir / "what_if_power_comparison.csv")
        self.assertEqual(len(what_if_df), 5)
        self.assertIn("projected_annual_savings_kWh", what_if_df.columns)

    def test_future_temperature_forecasting(self):
        df_extended = create_synthetic_telemetry(n=200)
        train_and_evaluate_temperature_forecast(
            df_extended,
            self.output_dir,
            target_metric="p0_vdd_temp",
            horizon_minutes=2.0,
            asset_id="M100_NODE_1",
            max_gap_seconds=60,
        )
        self.assertTrue((self.output_dir / "temperature_forecast_evaluation.csv").exists())
        self.assertTrue((self.output_dir / "future_temperature_predictions.csv").exists())
        self.assertTrue((self.output_dir / "standardized_prediction_record.json").exists())
        self.assertTrue((self.output_dir / "standardized_temperature_predictions.csv").exists())
        self.assertTrue((self.output_dir / "temperature_forecast_model.joblib").exists())
        self.assertTrue((self.output_dir / "future_temperature_forecast.png").exists())


if __name__ == "__main__":
    unittest.main()
