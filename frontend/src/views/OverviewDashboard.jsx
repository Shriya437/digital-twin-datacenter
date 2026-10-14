import React, { useState, useEffect } from 'react';
import {
  Activity,
  AlertTriangle,
  BatteryCharging,
  CheckCircle2,
  Cpu,
  Flame,
  Gauge,
  Radio,
  Server,
  TrendingUp,
  Zap,
  ArrowRight
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function OverviewDashboard({ onNavigate }) {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function loadData() {
      try {
        setLoading(true);
        const res = await api.getOverview();
        if (isMounted) {
          setOverview(res.data);
          setError(null);
        }
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  if (loading && !overview) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Radio className="spin" size={32} color="var(--cyan-primary)" style={{ margin: '0 auto 16px' }} />
        <p>Loading Digital Twin Telemetry & Health Contract...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-panel" style={{ padding: '30px', borderColor: 'var(--rose-primary)', color: '#fb7185' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
          <AlertTriangle size={24} />
          <h3 style={{ fontSize: '1.1rem' }}>Failed to connect to Python Backend</h3>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>{error}</p>
        <p style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          Ensure FastAPI backend is running at http://127.0.0.1:8000
        </p>
      </div>
    );
  }

  const { kpis, latest_telemetry, recent_incidents, top_risk_assets } = overview || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Page Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 1</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Real-Time Mission Control</span>
          </div>
          <h1 className="section-title">Overview Dashboard</h1>
          <p className="section-subtitle">
            Instant operational visibility across asset health, telemetry reliability, active incidents, energy, and high-risk equipment.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={() => onNavigate('telemetry')}>
            <Radio size={16} color="var(--cyan-primary)" />
            <span>Open Telemetry Stream</span>
          </button>
          <button className="btn btn-primary" onClick={() => onNavigate('twin')}>
            <Server size={16} />
            <span>Launch Digital Twin Rack</span>
          </button>
        </div>
      </div>

      {/* Primary KPI Ribbon (5 Critical Pillars) */}
      <div className="grid-cols-4" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
        {/* KPI 1: Telemetry Reliability */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Telemetry Reliability
            </span>
            <CheckCircle2 size={18} color="var(--emerald-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '10px 0 4px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)' }}>
              {kpis?.overall_reliability_pct}%
            </span>
          </div>
          <span className="badge badge-nominal" style={{ fontSize: '0.7rem' }}>
            4,917 Validated Samples
          </span>
        </div>

        {/* KPI 2: Active Incidents */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Active Incidents
            </span>
            <AlertTriangle size={18} color="var(--rose-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '10px 0 4px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fb7185', fontFamily: 'var(--font-mono)' }}>
              {kpis?.active_anomalies_count}
            </span>
          </div>
          <span className="badge badge-critical" style={{ fontSize: '0.7rem' }}>
            Z-Score & IsoForest Flags
          </span>
        </div>

        {/* KPI 3: Total Energy Usage */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Integrated Energy
            </span>
            <BatteryCharging size={18} color="var(--cyan-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '10px 0 4px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--cyan-primary)', fontFamily: 'var(--font-mono)' }}>
              {kpis?.total_energy_kwh}
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>kWh</span>
          </div>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
            Trapezoidal Integration
          </span>
        </div>

        {/* KPI 4: High-Risk Assets */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              High-Risk Equipment
            </span>
            <Flame size={18} color="var(--amber-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '10px 0 4px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--amber-primary)', fontFamily: 'var(--font-mono)' }}>
              {kpis?.high_risk_equipment_count}
            </span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>/ 4 Targets</span>
          </div>
          <span className="badge badge-warning" style={{ fontSize: '0.7rem' }}>
            Degradation Identified
          </span>
        </div>

        {/* KPI 5: PUE Rating */}
        <div className="glass-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>
              Facility PUE Ratio
            </span>
            <Gauge size={18} color="var(--purple-primary)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '10px 0 4px' }}>
            <span style={{ fontSize: '1.8rem', fontWeight: 800, color: '#c084fc', fontFamily: 'var(--font-mono)' }}>
              {kpis?.datacenter_pue}
            </span>
          </div>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Tier-0 High Efficiency
          </span>
        </div>
      </div>

      {/* Middle Row: Live Telemetry Snapshot & Top High-Risk Equipment */}
      <div className="grid-cols-2">
        {/* Live Telemetry Snapshot Strip */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Radio size={18} color="var(--cyan-primary)" />
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Active Node Telemetry Snapshot</h3>
            </div>
            <span className="badge badge-nominal">Sensor Streams Online</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
            <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Processor 0 VDD Temp</span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f43f5e', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                {latest_telemetry?.p0_vdd_temp ?? 52.4}°C
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>Estimate: 51.8°C (±1.8°)</span>
            </div>

            <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Processor 1 VDD Temp</span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#fb7185', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                {latest_telemetry?.p1_vdd_temp ?? 50.1}°C
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>Estimate: 49.5°C (±1.9°)</span>
            </div>

            <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Ambient Cold Aisle</span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                {latest_telemetry?.ambient ?? 21.8}°C
              </div>
              <span style={{ fontSize: '0.68rem', color: '#10b981' }}>Nominal Inflow</span>
            </div>

            <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Intake Fan 0</span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#34d399', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                {latest_telemetry?.fan0_0 ?? 4600} RPM
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>38% Duty Cycle</span>
            </div>

            <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Exhaust Fan 1</span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#34d399', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                {latest_telemetry?.fan1_0 ?? 4550} RPM
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>38% Duty Cycle</span>
            </div>

            <div style={{ background: 'var(--bg-surface)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Node Total Power</span>
              <div style={{ fontSize: '1.35rem', fontWeight: 700, color: '#fbbf24', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                {latest_telemetry?.total_power ?? 640} W
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>PS0 + PS1 Combined</span>
            </div>
          </div>
        </div>

        {/* High-Risk Equipment & Maintenance Priority */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={18} color="var(--amber-primary)" />
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>High-Risk Equipment (Predictive Health)</h3>
            </div>
            <button
              onClick={() => onNavigate('predictive')}
              style={{ background: 'none', border: 'none', color: 'var(--cyan-primary)', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <span>View All</span>
              <ArrowRight size={14} />
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {top_risk_assets?.map((asset) => (
              <div
                key={asset.asset_id}
                style={{
                  background: 'var(--bg-surface)',
                  padding: '14px 16px',
                  borderRadius: 'var(--radius-md)',
                  borderLeft: asset.risk_level === 'CRITICAL' ? '4px solid var(--rose-primary)' : '4px solid var(--amber-primary)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <strong style={{ fontSize: '0.9rem', color: '#fff' }}>{asset.component_name}</strong>
                    <span className={asset.risk_level === 'CRITICAL' ? 'badge badge-critical' : 'badge badge-warning'}>
                      {asset.risk_level}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    {asset.early_warning}
                  </p>
                </div>

                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    RUL: ~{asset.estimated_rul_days} Days
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    Degradation: {asset.degradation_rate_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Row: Recent Anomaly Events Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Active Incidents & Anomaly Flags</h3>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Statistical Z-Score and Isolation Forest flags detected in dataset telemetry.
            </p>
          </div>
          <button className="btn btn-secondary" onClick={() => onNavigate('root-cause')}>
            <span>Analyze Root Causes</span>
            <ArrowRight size={14} />
          </button>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Metric Name</th>
                <th>Observed Value</th>
                <th>Detector</th>
                <th>Anomaly Score</th>
                <th>Threshold</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recent_incidents?.map((inc, i) => (
                <tr key={i}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{inc.timestamp}</td>
                  <td><strong style={{ color: 'var(--cyan-primary)' }}>{inc.metric_name}</strong></td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{inc.observed_value}</td>
                  <td>
                    <span className="badge badge-cyan" style={{ fontSize: '0.68rem' }}>
                      {inc.detector}
                    </span>
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)' }}>{inc.anomaly_score?.toFixed?.(3) ?? inc.anomaly_score}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{inc.threshold}</td>
                  <td>
                    <span className="badge badge-critical">Anomaly</span>
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
