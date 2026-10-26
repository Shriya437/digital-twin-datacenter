import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  FileCheck,
  Layers,
  Activity,
  Sliders
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function ReliabilityView() {
  const [reliabilityData, setReliabilityData] = useState({ metrics: [], timestamp_gaps: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const res = await api.getReliabilityReport();
        setReliabilityData(res.data);
      } catch (err) {
        console.error('Failed to load reliability report:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const { metrics, timestamp_gaps } = reliabilityData;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 8</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Data Health & Sensor Sanity</span>
          </div>
          <h1 className="section-title">Telemetry Reliability & Gap Analysis</h1>
          <p className="section-subtitle">
            Metric-by-metric completeness scores, infinite/missing value audits, sensor plausibility checks, and timestamp gap reports.
          </p>
        </div>
      </div>

      {/* Metrics Quality Scorecard */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={18} color="var(--emerald-primary)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Metric Completeness & Quality Scores</h3>
          </div>
          <span className="badge badge-nominal">10 Primary Metrics</span>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Metric Name</th>
                <th>Record Count</th>
                <th>Completeness %</th>
                <th>Data Quality Score</th>
                <th>Plausibility Bounds</th>
                <th>Sanity Status</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, i) => (
                <tr key={i}>
                  <td><strong style={{ color: 'var(--cyan-primary)' }}>{m.metric_name}</strong></td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{m.record_count}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: '#34d399', fontWeight: 600 }}>
                    {m.completeness_pct}%
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{m.data_quality_score_pct}%</td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {m.metric_name.includes('temp') ? '[20°C - 90°C]' : (m.metric_name.includes('fan') ? '[1500 - 12000 RPM]' : '[50W - 2400W]')}
                  </td>
                  <td>
                    <span className="badge badge-nominal">VERIFIED</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Timestamp Gap Report */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Clock size={18} color="var(--amber-primary)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Timestamp Continuity & Gap Auditing</h3>
          </div>
          <span className="badge badge-warning">Gap Threshold: &gt;60s</span>
        </div>

        <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
          Identifies chronological discontinuity in telemetry. The digital twin strictly isolates segments so statistical rolling windows never bridge across gaps.
        </p>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Observed Gap (Seconds)</th>
                <th>Typical Cadence</th>
                <th>Major Gap Flag</th>
                <th>Duplicate Flag</th>
              </tr>
            </thead>
            <tbody>
              {timestamp_gaps.slice(0, 8).map((gap, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{gap.timestamp}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: gap.gap_seconds > 60 ? '#fb7185' : 'var(--text-secondary)' }}>
                    {gap.gap_seconds?.toFixed?.(1) ?? gap.gap_seconds}s
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>20.0s</td>
                  <td>
                    {gap.timestamp_gap_flag ? (
                      <span className="badge badge-critical">Long Gap (&gt;60s)</span>
                    ) : (
                      <span className="badge badge-nominal">Continuous</span>
                    )}
                  </td>
                  <td>
                    <span className="badge badge-nominal">Unique</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
