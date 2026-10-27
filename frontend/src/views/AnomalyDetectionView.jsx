import React, { useState, useMemo } from 'react';
import MetricCard from '../components/MetricCard';
import ChartPanel from '../components/ChartPanel';
import StatusBadge from '../components/StatusBadge';
import { useAnomalies } from '../hooks/useAnomalies';
import { useTelemetry } from '../hooks/useTelemetry';

/**
 * AnomalyDetectionView Component
 * Analyzes outputs from the Isolation Forest and PCA reconstruction error detectors.
 * Distinguishes detector-specific thresholds, score distributions, and flagged sensor records.
 */
export default function AnomalyDetectionView() {
  const {
    anomalies,
    latestAnomalyResult,
    detectorMetadata,
    loading: anomLoading,
    error: anomError
  } = useAnomalies({ limit: 100 });

  const { history, loading: telLoading } = useTelemetry({ historyLimit: 40 });

  const [selectedDetector, setSelectedDetector] = useState('all'); // 'all' | 'isolation_forest' | 'pca'
  const [selectedRecord, setSelectedRecord] = useState(null);

  // Filter flagged records based on active detector selection
  const filteredAnomalies = useMemo(() => {
    if (!Array.isArray(anomalies)) return [];
    if (selectedDetector === 'all') return anomalies;
    return anomalies.filter((a) => {
      const det = (a.detector || a.method || '').toLowerCase();
      if (selectedDetector === 'isolation_forest') return det.includes('isolation') || det.includes('forest');
      if (selectedDetector === 'pca') return det.includes('pca');
      return true;
    });
  }, [anomalies, selectedDetector]);

  // Map history to Anomaly Score distribution time-series for ChartPanel
  const anomalyScoreChartData = useMemo(() => {
    return history
      .map((row) => ({
        timestamp: row.timestamp
          ? new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : '—',
        value: typeof row.anomaly_score === 'number'
          ? Number(row.anomaly_score.toFixed(3))
          : typeof row.score === 'number'
          ? Number(row.score.toFixed(3))
          : 0.04, // Nominal baseline score representation if not explicitly scored
        is_anomaly: Boolean(row.is_anomaly)
      }))
      .filter((pt) => pt.value !== null);
  }, [history]);

  // Extract detector configuration thresholds safely
  const isoContamination = detectorMetadata?.contamination ?? 0.01;
  const pcaResidualThreshold = detectorMetadata?.pca_threshold ?? 0.045;
  const currentIsoScore = latestAnomalyResult?.score ?? 'Unavailable';
  const currentPcaResidual = latestAnomalyResult?.pca_residual ?? 'Unavailable';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header Description */}
      <div>
        <h2 className="gradient-text-aurora" style={{ margin: 0, fontSize: '18px', color: '#f8fafc', fontWeight: 700 }}>
          ML Anomaly Detection & Statistical Outlier Analysis
        </h2>
        <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
          Unsupervised multidimensional anomaly detection trained on held-out Marconi-100 telemetry.
        </p>
      </div>

      {/* KPI Cards: Detector Specific Thresholds and Current Readings */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        <MetricCard
          title="Isolation Forest Score"
          value={typeof currentIsoScore === 'number' ? currentIsoScore.toFixed(3) : currentIsoScore}
          status={latestAnomalyResult?.is_anomaly ? 'ANOMALOUS' : currentIsoScore !== 'Unavailable' ? 'HEALTHY' : 'UNAVAILABLE'}
          source="IsolationForest (n=100)"
          subtext={`Contamination threshold: ${isoContamination}`}
          icon="⚠"
        />

        <MetricCard
          title="PCA Reconstruction Residual"
          value={typeof currentPcaResidual === 'number' ? currentPcaResidual.toFixed(3) : currentPcaResidual}
          status={
            typeof currentPcaResidual === 'number'
              ? currentPcaResidual > pcaResidualThreshold ? 'WARNING' : 'HEALTHY'
              : 'UNAVAILABLE'
          }
          source="PCA (8 Principal Comps)"
          subtext={`Threshold: ${pcaResidualThreshold}`}
          icon="⛨"
        />

        <MetricCard
          title="Flagged Observations"
          value={anomalies.length}
          status={anomalies.length > 0 ? 'WARNING' : 'HEALTHY'}
          source="Active Dataset Slice"
          subtext={anomLoading ? 'Evaluating window...' : 'Held-out validation stream'}
          icon="⚡"
        />

        <MetricCard
          title="Active Model Status"
          value={anomError ? 'Error' : 'Operational'}
          status={anomError ? 'CRITICAL' : 'OPTIMAL'}
          source="Predictive Service"
          subtext={anomError || 'Pipelines synchronized'}
          icon="✓"
        />
      </div>

      {/* Anomaly Score Distribution Chart */}
      <ChartPanel
        title="Multidimensional Anomaly Score Trajectory Over Telemetry Stream"
        historicalData={anomalyScoreChartData}
        forecastData={[]}
        yKey="value"
        unit=""
        height={260}
      />

      {/* Filter and Anomaly Evidence Records Table */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.85)',
          border: '1px solid rgba(56, 189, 248, 0.18)',
          borderRadius: '10px',
          padding: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
              Flagged Telemetry Observations
            </span>
            <span style={{ fontSize: '11px', color: '#64748b', marginLeft: '8px' }}>
              ({filteredAnomalies.length} observations exceeding detector decision boundary)
            </span>
          </div>

          {/* Detector Filter Toggle */}
          <div style={{ display: 'flex', gap: '6px' }}>
            {[
              { id: 'all', label: 'All Detectors' },
              { id: 'isolation_forest', label: 'Isolation Forest' },
              { id: 'pca', label: 'PCA Residuals' }
            ].map((btn) => (
              <button
                key={btn.id}
                onClick={() => setSelectedDetector(btn.id)}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: selectedDetector === btn.id ? '1px solid #00f2fe' : '1px solid rgba(56, 189, 248, 0.15)',
                  backgroundColor: selectedDetector === btn.id ? 'rgba(14, 165, 233, 0.2)' : 'rgba(30, 41, 59, 0.4)',
                  color: selectedDetector === btn.id ? '#00f2fe' : '#94a3b8'
                }}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>

        {/* Flagged Records Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(51, 65, 85, 0.6)', color: '#94a3b8' }}>
                <th style={{ padding: '8px 12px' }}>Timestamp</th>
                <th style={{ padding: '8px 12px' }}>Detector</th>
                <th style={{ padding: '8px 12px' }}>Score / Residual</th>
                <th style={{ padding: '8px 12px' }}>Recorded Power (W)</th>
                <th style={{ padding: '8px 12px' }}>Core Temp (°C)</th>
                <th style={{ padding: '8px 12px' }}>Fan Speed (RPM)</th>
                <th style={{ padding: '8px 12px' }}>Decision</th>
              </tr>
            </thead>
            <tbody>
              {filteredAnomalies.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                    {anomLoading
                      ? 'Evaluating sensor records...'
                      : 'No anomaly records flagged by detector models in the active window.'}
                  </td>
                </tr>
              ) : (
                filteredAnomalies.map((rec, idx) => {
                  const isSelected = selectedRecord === idx;
                  return (
                    <tr
                      key={idx}
                      onClick={() => setSelectedRecord(isSelected ? null : idx)}
                      style={{
                        borderBottom: '1px solid rgba(51, 65, 85, 0.35)',
                        backgroundColor: isSelected ? 'rgba(14, 165, 233, 0.12)' : 'transparent',
                        cursor: 'pointer'
                      }}
                    >
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#cbd5e1' }}>
                        {rec.timestamp || 'Recorded Observation'}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#38bdf8' }}>
                        {rec.detector || rec.method || 'Isolation Forest'}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontWeight: 600, color: '#f87171' }}>
                        {typeof rec.anomaly_score === 'number'
                          ? rec.anomaly_score.toFixed(3)
                          : typeof rec.score === 'number'
                          ? rec.score.toFixed(3)
                          : 'Flagged'}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#cbd5e1' }}>
                        {typeof rec.total_power === 'number'
                          ? `${rec.total_power.toFixed(1)} W`
                          : typeof rec.power === 'number'
                          ? `${rec.power.toFixed(1)} W`
                          : (rec.total_power || rec.power || '—')}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#cbd5e1' }}>
                        {typeof rec.temp_core_max === 'number'
                          ? `${rec.temp_core_max.toFixed(1)} °C`
                          : typeof rec.p0_vdd_temp === 'number'
                          ? `${rec.p0_vdd_temp.toFixed(1)} °C`
                          : typeof rec.temperature === 'number'
                          ? `${rec.temperature.toFixed(1)} °C`
                          : (rec.temp_core_max || rec.p0_vdd_temp || '—')}
                      </td>
                      <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: '#cbd5e1' }}>
                        {typeof rec.fan_rpm === 'number'
                          ? `${Math.round(rec.fan_rpm).toLocaleString()} RPM`
                          : typeof rec.fan0_0 === 'number'
                          ? `${Math.round(rec.fan0_0).toLocaleString()} RPM`
                          : (rec.fan_rpm || rec.fan0_0 || '—')}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <StatusBadge status="ANOMALOUS" size="sm" />
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Selected Record Detail Drill-down */}
        {selectedRecord !== null && filteredAnomalies[selectedRecord] && (
          <div
            style={{
              marginTop: '12px',
              padding: '14px',
              backgroundColor: 'rgba(30, 41, 59, 0.65)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: '8px',
              fontSize: '12px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontWeight: 600, color: '#38bdf8' }}>
                Anomaly Feature Departure Evidence & Telemetry Snapshot
              </span>
              <button
                onClick={() => setSelectedRecord(null)}
                style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '13px' }}
              >
                ✕ Close
              </button>
            </div>
            <p style={{ color: '#cbd5e1', lineHeight: 1.5, margin: '0 0 10px 0' }}>
              Observation at <strong>{filteredAnomalies[selectedRecord].timestamp}</strong> was flagged by detector{' '}
              <strong style={{ color: '#38bdf8' }}>{filteredAnomalies[selectedRecord].detector || filteredAnomalies[selectedRecord].method}</strong> with anomaly score{' '}
              <strong style={{ color: '#f87171' }}>
                {filteredAnomalies[selectedRecord].anomaly_score ?? filteredAnomalies[selectedRecord].score}
              </strong>
              {filteredAnomalies[selectedRecord].threshold ? ` (decision boundary: ${Number(filteredAnomalies[selectedRecord].threshold).toFixed(2)})` : ''}.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '8px' }}>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '6px 10px', borderRadius: '4px' }}>
                <div style={{ color: '#94a3b8', fontSize: '10px' }}>TOTAL POWER</div>
                <div style={{ color: '#00f2fe', fontWeight: 600, fontFamily: 'monospace' }}>
                  {filteredAnomalies[selectedRecord].total_power ?? filteredAnomalies[selectedRecord].power ?? '—'} W
                </div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '6px 10px', borderRadius: '4px' }}>
                <div style={{ color: '#94a3b8', fontSize: '10px' }}>CORE TEMP (P0 / P1)</div>
                <div style={{ color: '#f87171', fontWeight: 600, fontFamily: 'monospace' }}>
                  {filteredAnomalies[selectedRecord].p0_vdd_temp ?? filteredAnomalies[selectedRecord].temp_core_max ?? '—'}°C / {filteredAnomalies[selectedRecord].p1_vdd_temp ?? '—'}°C
                </div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '6px 10px', borderRadius: '4px' }}>
                <div style={{ color: '#94a3b8', fontSize: '10px' }}>FAN TACHOMETERS</div>
                <div style={{ color: '#34d399', fontWeight: 600, fontFamily: 'monospace' }}>
                  {filteredAnomalies[selectedRecord].fan0_0 ?? filteredAnomalies[selectedRecord].fan_rpm ?? '—'} / {filteredAnomalies[selectedRecord].fan1_0 ?? '—'} RPM
                </div>
              </div>
              <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '6px 10px', borderRadius: '4px' }}>
                <div style={{ color: '#94a3b8', fontSize: '10px' }}>AMBIENT AIR</div>
                <div style={{ color: '#cbd5e1', fontWeight: 600, fontFamily: 'monospace' }}>
                  {filteredAnomalies[selectedRecord].ambient ? `${filteredAnomalies[selectedRecord].ambient}°C` : '—'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}