import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../api/client';

/**
 * useModelMetrics Hook
 * Fetches verification and evaluation metrics computed on held-out test splits
 * across all ML models: Isolation Forest, PCA, Regressors, and Dependency Graphs.
 */
export function useModelMetrics() {
  const [models, setModels] = useState([]);
  const [overallPipelineStatus, setOverallPipelineStatus] = useState('UNKNOWN');
  const [dataReliabilityReport, setDataReliabilityReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const isMountedRef = useRef(true);

  const fetchModelMetrics = useCallback(async () => {
    try {
      // Fetch model verification and evaluation reports
      const [evalRes, relRes] = await Promise.allSettled([
        apiClient.get('/predictive/models/evaluation'),
        apiClient.get('/reliability/report')
      ]);

      if (!isMountedRef.current) return;

      let modelList = [];
      if (evalRes.status === 'fulfilled' && evalRes.value?.data) {
        const evalData = evalRes.value.data;
        modelList = Array.isArray(evalData)
          ? evalData
          : (evalData.models || []);
        setOverallPipelineStatus(evalData.pipeline_status || 'HEALTHY');
      }

      if (relRes.status === 'fulfilled' && relRes.value?.data) {
        setDataReliabilityReport(relRes.value.data);
      }

      setModels(modelList);
      setError(null);
    } catch (err) {
      if (!isMountedRef.current) return;
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch ML model evaluation reports';
      setError(msg);
      setModels([]);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    isMountedRef.current = true;
    fetchModelMetrics();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchModelMetrics]);

  const refetch = useCallback(() => {
    setLoading(true);
    return fetchModelMetrics();
  }, [fetchModelMetrics]);

  return {
    models,
    overallPipelineStatus,
    dataReliabilityReport,
    loading,
    error,
    refetch
  };
}