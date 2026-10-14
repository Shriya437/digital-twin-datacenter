import React, { useState, useEffect } from 'react';
import {
  Wrench,
  AlertTriangle,
  Clock,
  TrendingDown,
  ArrowRight,
  ShieldAlert,
  Sliders,
  CheckCircle2,
  Calendar,
  Layers,
  Activity,
  Flame
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function PredictiveMaintenanceView({ onNavigate }) {
  const [rankedAssets, setRankedAssets] = useState([]);
  const [forecasts, setForecasts] = useState(null);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [selectedHorizon, setSelectedHorizon] = useState('15min'); // '1min', '5min', '15min'
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [assetsRes, forecastsRes] = await Promise.all([
          api.getPredictiveAssets(),
          api.getForecasts()
        ]);
        setRankedAssets(assetsRes.data);
        if (assetsRes.data?.length > 0) setSelectedAsset(assetsRes.data[0]);
        setForecasts(forecastsRes.data);
      } catch (err) {
        console.error('Failed to load predictive maintenance data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const samplePoints = forecasts?.sample_forecasts?.[`p0_${selectedHorizon}`] || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 4</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Proactive Equipment Lifecycle</span>
          </div>
          <h1 className="section-title">Predictive Maintenance & Degradation</h1>
          <p className="section-subtitle">
            Risk-ranked asset list with early warnings, predicted downstream impacts, scheduled maintenance tasks, and what-if simulations.
          </p>
        </div>

        <button className="btn btn-primary" onClick={() => onNavigate('energy')}>
          <Sliders size={16} />
          <span>Launch What-If Simulator</span>
        </button>
      </div>

      {/* Main Grid: Left = Risk-Ranked Asset List, Right = Horizon Forecasting Curve */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '24px' }}>
        {/* Left: Risk-Ranked Asset List */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Wrench size={18} color="var(--cyan-primary)" />
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Risk-Ranked Critical Assets</h3>
            </div>
            <span className="badge badge-warning">RUL & Degradation Models</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {rankedAssets.map((asset) => {
              const isSelected = selectedAsset?.asset_id === asset.asset_id;
              const isCritical = asset.risk_level === 'CRITICAL';
              const isHigh = asset.risk_level === 'HIGH';

              return (
                <div
                  key={asset.asset_id}
                  onClick={() => setSelectedAsset(asset)}
                  style={{
                    background: isSelected ? 'rgba(0, 242, 254, 0.08)' : 'var(--bg-surface)',
                    border: isSelected ? '1px solid var(--cyan-primary)' : '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '18px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: isSelected ? '0 0 15px rgba(0, 242, 254, 0.15)' : 'none'
                  }}
                >
                  {/* Top row */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{
                        width: '26px',
                        height: '26px',
                        borderRadius: '6px',
                        background: isCritical ? 'rgba(244, 63, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                        border: isCritical ? '1px solid var(--rose-primary)' : '1px solid var(--amber-primary)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.8rem',
                        fontWeight: 800,
                        color: isCritical ? '#fb7185' : '#fbbf24',
                        fontFamily: 'var(--font-mono)'
                      }}>
                        #{asset.rank}
                      </span>
                      <div>
                        <strong style={{ fontSize: '0.95rem', color: '#fff' }}>{asset.component_name}</strong>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{asset.asset_id} • {asset.type}</div>
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <span className={isCritical ? 'badge badge-critical' : (isHigh ? 'badge badge-warning' : 'badge badge-nominal')}>
                        {asset.risk_level} ({Math.round(asset.risk_score * 100)}%)
                      </span>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
                        RUL: ~{asset.estimated_rul_days} Days
                      </div>
                    </div>
                  </div>

                  {/* Early Warning Banner */}
                  <div style={{
                    background: 'rgba(0, 0, 0, 0.35)',
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-sm)',
                    borderLeft: `3px solid ${isCritical ? 'var(--rose-primary)' : 'var(--amber-primary)'}`,
                    marginBottom: '12px'
                  }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 600 }}>Early Warning Indicator:</span>
                    <p style={{ fontSize: '0.78rem', color: '#fff', marginTop: '2px', lineHeight: 1.4 }}>
                      {asset.early_warning}
                    </p>
                  </div>

                  {/* Predicted Downstream Impacts */}
                  <div style={{ marginBottom: '14px' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                      Predicted Downstream Impacts ({asset.predicted_downstream_impacts.length}):
                    </span>
                    <ul style={{ margin: '4px 0 0 16px', fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {asset.predicted_downstream_impacts.map((imp, idx) => (
                        <li key={idx}>{imp}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Actionable Maintenance & What-If Link Bar */}
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    background: 'rgba(255, 255, 255, 0.03)',
                    padding: '10px 12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    flexWrap: 'wrap',
                    gap: '10px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Calendar size={14} color="var(--cyan-primary)" />
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-primary)' }}>
                        Task: <strong>{asset.maintenance_task.id}</strong> ({asset.maintenance_task.title})
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '0.72rem' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onNavigate('decision');
                        }}
                      >
                        Schedule Task
                      </button>

                      <button
                        className="btn btn-primary"
                        style={{ padding: '4px 10px', fontSize: '0.72rem' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onNavigate('energy');
                        }}
                      >
                        Simulate What-If
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right: Multi-Horizon Forecast Curves */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Multi-Horizon Temperature Forecasting</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Random Forest & HistGradientBoosting models predicting thermal trajectory.
                </p>
              </div>

              {/* Horizon Tabs */}
              <div style={{ display: 'flex', background: 'var(--bg-surface)', padding: '2px', borderRadius: 'var(--radius-sm)' }}>
                {['1min', '5min', '15min'].map((h) => (
                  <button
                    key={h}
                    onClick={() => setSelectedHorizon(h)}
                    style={{
                      background: selectedHorizon === h ? 'var(--cyan-primary)' : 'transparent',
                      color: selectedHorizon === h ? '#000' : 'var(--text-muted)',
                      border: 'none',
                      padding: '4px 10px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      cursor: 'pointer'
                    }}
                  >
                    +{h.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            {/* Forecast Plot */}
            <div style={{ width: '100%', height: '260px', background: 'rgba(0,0,0,0.3)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
              <svg viewBox="0 0 500 200" style={{ width: '100%', height: '100%' }}>
                {/* Horizontal thermal threshold line (85°C critical limit) */}
                <line x1="30" y1="50" x2="480" y2="50" stroke="#f43f5e" strokeWidth="1.5" strokeDasharray="4 4" />
                <text x="35" y="44" fill="#fb7185" fontSize="9" fontFamily="var(--font-mono)">SAFETY THRESHOLD: 85°C</text>

                {/* Grid */}
                {[40, 60, 80].map((t) => {
                  const y = 180 - ((t - 30) / 60) * 150;
                  return (
                    <g key={t}>
                      <line x1="30" y1={y} x2="480" y2={y} stroke="rgba(255,255,255,0.06)" />
                      <text x="10" y={y + 3} fill="var(--text-dim)" fontSize="8">{t}°</text>
                    </g>
                  );
                })}

                {/* Forecast Line */}
                {samplePoints.length > 1 && (
                  <path
                    d={samplePoints.slice(0, 40).reduce((acc, pt, i) => {
                      const x = 30 + (i / 39) * 450;
                      const temp = pt.predicted_future_temperature || pt.target_value || 52;
                      const y = 180 - ((temp - 30) / 60) * 150;
                      return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
                    }, '')}
                    fill="none"
                    stroke="var(--cyan-primary)"
                    strokeWidth="2.5"
                  />
                )}
              </svg>
            </div>

            <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'space-between', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
              <span>Target Metric: <strong>p0_vdd_temp</strong></span>
              <span>Horizon: <strong>{selectedHorizon} Ahead</strong></span>
              <span>Selected Model: <strong>HistGradientBoostingRegressor</strong></span>
            </div>
          </div>

          {/* Model Accuracy & Evaluation Metrics */}
          <div className="glass-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '12px' }}>
              Model Validation & Evaluation Metrics
            </h3>

            <div className="data-table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Target</th>
                    <th>Horizon</th>
                    <th>MAE</th>
                    <th>Selected Model</th>
                  </tr>
                </thead>
                <tbody>
                  {forecasts?.metrics_summary?.map((m, i) => (
                    <tr key={i}>
                      <td><strong style={{ color: 'var(--text-primary)' }}>{m.target}</strong></td>
                      <td><span className="badge badge-cyan">{m.horizon_minutes}m</span></td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: '#34d399', fontWeight: 600 }}>{m.MAE?.toFixed?.(3) ?? m.MAE}°C</td>
                      <td style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{m.selected_model}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
