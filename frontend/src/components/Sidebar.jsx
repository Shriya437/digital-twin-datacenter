import React from 'react';

/**
 * Sidebar Component
 * Multi-view navigation menu for all 10 specialized data center operations.
 */
export default function Sidebar({ activeView, onViewChange }) {
  const navItems = [
    { id: 'overview', label: '01 Overview Dashboard', icon: '▦' },
    { id: 'digital-twin', label: '02 3D Digital Twin View', icon: '❖' },
    { id: 'predictive-maintenance', label: '03 Predictive Maintenance', icon: '⚙' },
    { id: 'anomaly-detection', label: '04 ML Anomaly Detection', icon: '⚠' },
    { id: 'forecasting', label: '05 Temperature Forecasts', icon: '↗' },
    { id: 'root-cause', label: '06 Root Cause Diagnostics', icon: '⚲' },
    { id: 'energy-analytics', label: '07 Energy & Power Analytics', icon: '⚡' },
    { id: 'reliability', label: '08 Telemetry Reliability', icon: '⛨' },
    { id: 'telemetry-explorer', label: '09 Dataset Explorer', icon: '≡' },
    { id: 'model-performance', label: '10 ML Model Evaluation', icon: '✓' }
  ];

  return (
    <aside
      style={{
        width: '260px',
        backgroundColor: '#0a1128',
        borderRight: '1px solid rgba(56, 189, 248, 0.12)',
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 62px)',
        position: 'sticky',
        top: '62px',
        overflowY: 'auto'
      }}
    >
      <div style={{ padding: '16px 14px 8px', fontSize: '11px', fontWeight: 600, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
        Operational Views
      </div>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px', padding: '0 8px' }}>
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: 'none',
                background: isActive
                  ? 'linear-gradient(90deg, rgba(14, 165, 233, 0.2) 0%, rgba(14, 165, 233, 0.05) 100%)'
                  : 'transparent',
                borderLeft: isActive ? '3px solid #00f2fe' : '3px solid transparent',
                color: isActive ? '#38bdf8' : '#94a3b8',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.18s ease'
              }}
            >
              <span style={{ fontSize: '15px', color: isActive ? '#00f2fe' : '#64748b' }}>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div style={{ marginTop: 'auto', padding: '16px', borderTop: '1px solid rgba(56, 189, 248, 0.08)', fontSize: '11px', color: '#475569' }}>
        <div>HPC Twin System v2.4</div>
        <div style={{ color: '#00f2fe', marginTop: '2px' }}>Marconi-100 Cluster Node</div>
      </div>
    </aside>
  );
}