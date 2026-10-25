import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../api/client';

/**
 * useForecasts Hook
 * Fetches model-generated predictions (e.g., Ridge / Random Forest regressor horizons)
 * and corresponding evaluation metrics (RMSE, MAE).
 *
 * @param {Object} options
 * @param {number} options.horizonMinutes Forecast horizon in minutes (e.g., 15, 30).
 * @param {string} options.targetVariable Target variable name ('temp_core_max', 'total_power').
 * @param {string} options.nodeId Target node identifier.
 */
export function useForecasts({
  horizonMinutes = 15,
  targetVariable = 'temp_core_max',
  nodeId = 'node1'
} = {}) {
  const [comparisonData, setComparisonData] = useState([]);
  const [forwardProjection, setForwardProjection] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [modelMetrics, setModelMetrics] = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const isMountedRef = useRef(true);

  const fetchForecasts = useCallback(async () => {
    try {
      const response = await apiClient.get('/predictive/forecast', {
        params: {
          node_id: nodeId,
          horizon: horizonMinutes,
          target: targetVariable
        }
      });

      if (!isMountedRef.current) return;

      const data = response?.data || {};

      const forecastList = Array.isArray(data.forecasts)
        ? data.forecasts
        : Array.isArray(data.predictions)
        ? data.predictions
        : [];

      setForecasts(forecastList);
      setComparisonData(Array.isArray(data.comparison_data) ? data.comparison_data : []);
      setForwardProjection(Array.isArray(data.forward_projection) ? data.forward_projection : []);
      setModelMetrics(data.metrics || null);
      setModelInfo({
        modelName: data.model_name || data.algorithm || 'Ridge/RandomForest Ensemble',
        modelVersion: data.model_version || '1.0',
        trainingWindow: data.training_window || null,
        targetVariable: data.target_variable || targetVariable
      });
      setError(null);
    } catch (err) {
      if (!isMountedRef.current) return;
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch ML forecasts';
      setError(msg);
      setForecasts([]);
      setComparisonData([]);
      setForwardProjection([]);
      setModelMetrics(null);
      setModelInfo(null);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [nodeId, horizonMinutes, targetVariable]);

  useEffect(() => {
    isMountedRef.current = true;
    fetchForecasts();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchForecasts]);

  const refetch = useCallback(() => {
    setLoading(true);
    return fetchForecasts();
  }, [fetchForecasts]);

  return {
    forecasts,
    comparisonData,
    forwardProjection,
    modelMetrics,
    modelInfo,
    loading,
    error,
    refetch
  };
}