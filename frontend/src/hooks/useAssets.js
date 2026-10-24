import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient } from '../api/client';

/**
 * useAssets Hook
 * Fetches asset inventory, physical rack topology, and node hardware specifications.
 * Also fetches live asset-level telemetry for a selected asset.
 *
 * @param {string|null} selectedAssetId Target asset ID to inspect (optional).
 */
export function useAssets(selectedAssetId = null) {
  const [assets, setAssets] = useState([]);
  const [selectedAssetDetail, setSelectedAssetDetail] = useState(null);
  const [topology, setTopology] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState(null);

  const isMountedRef = useRef(true);

  // 1. Fetch entire rack & node registry
  const fetchAssetRegistry = useCallback(async () => {
    try {
      const response = await apiClient.get('/assets/registry');
      if (!isMountedRef.current) return;

      const data = response?.data || {};
      const assetList = Array.isArray(data) ? data : (data.assets || []);
      setAssets(assetList);
      setTopology(data.topology || null);
      setError(null);
    } catch (err) {
      if (!isMountedRef.current) return;
      // Graceful fallback to twin service if assets/registry endpoint is partitioned
      try {
        const twinRes = await apiClient.get('/twin/state');
        if (!isMountedRef.current) return;
        setAssets(twinRes.data?.nodes || []);
        setTopology(twinRes.data?.topology || null);
        setError(null);
      } catch (fallbackErr) {
        if (!isMountedRef.current) return;
        const msg = err.response?.data?.detail || err.message || 'Failed to fetch asset inventory';
        setError(msg);
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  // 2. Fetch specific asset detail when selected
  const fetchAssetDetail = useCallback(async (assetId) => {
    if (!assetId) {
      setSelectedAssetDetail(null);
      return;
    }

    setDetailLoading(true);
    try {
      const response = await apiClient.get(`/assets/${encodeURIComponent(assetId)}`);
      if (!isMountedRef.current) return;
      setSelectedAssetDetail(response?.data || null);
    } catch (err) {
      if (!isMountedRef.current) return;
      // If single-asset route is unavailable, find it in the current asset list
      setSelectedAssetDetail((prev) => {
        const found = assets.find((a) => a.id === assetId || a.node_id === assetId);
        return found || null;
      });
    } finally {
      if (isMountedRef.current) {
        setDetailLoading(false);
      }
    }
  }, [assets]);

  useEffect(() => {
    isMountedRef.current = true;
    fetchAssetRegistry();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchAssetRegistry]);

  useEffect(() => {
    if (selectedAssetId) {
      fetchAssetDetail(selectedAssetId);
    } else {
      setSelectedAssetDetail(null);
    }
  }, [selectedAssetId, fetchAssetDetail]);

  return {
    assets,
    selectedAssetDetail,
    topology,
    loading,
    detailLoading,
    error,
    refetchAssets: fetchAssetRegistry,
    fetchAssetDetail
  };
}