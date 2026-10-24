import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../api/client';

/**
 * useTelemetry Hook
 * Fetches actual telemetry observations from the Marconi-100 dataset.
 *
 * @param {Object} options
 * @param {number} options.pollIntervalMs Polling frequency in ms (0 to disable polling).
 * @param {number} options.historyLimit Number of historical records to query.
 * @param {string} options.nodeId Target node identifier (defaults to 'node1').
 */
export function useTelemetry({
  pollIntervalMs = 5000,
  historyLimit = 30,
  nodeId = 'node1'
} = {}) {
  const [latestTelemetry, setLatestTelemetry] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const isMountedRef = useRef(true);

  const fetchTelemetry = useCallback(async () => {
    try {
      // 1. Fetch latest observation
      const latestRes = await apiClient.get('/data/latest', {
        params: { node_id: nodeId }
      });

      // 2. Fetch recent historical slice for time-series charts
      const historyRes = await apiClient.get('/data/history', {
        params: { node_id: nodeId, limit: historyLimit }
      });

      if (!isMountedRef.current) return;

      const latestData = latestRes?.data || null;
      const historyData = Array.isArray(historyRes?.data)
        ? historyRes.data
        : (historyRes?.data?.records || []);

      setLatestTelemetry(latestData);
      setHistory(historyData);
      setError(null);
    } catch (err) {
      if (!isMountedRef.current) return;
      const msg = err.response?.data?.detail || err.message || 'Failed to fetch telemetry data';
      setError(msg);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, [nodeId, historyLimit]);

  useEffect(() => {
    isMountedRef.current = true;
    fetchTelemetry();

    let intervalId = null;
    if (pollIntervalMs > 0) {
      intervalId = setInterval(fetchTelemetry, pollIntervalMs);
    }

    return () => {
      isMountedRef.current = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [fetchTelemetry, pollIntervalMs]);

  const refetch = useCallback(() => {
    setLoading(true);
    return fetchTelemetry();
  }, [fetchTelemetry]);

  return {
    latestTelemetry,
    history,
    loading,
    error,
    refetch
  };
}