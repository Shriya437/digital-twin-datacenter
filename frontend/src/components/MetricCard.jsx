import React from 'react';
import StatusBadge from './StatusBadge';

/**
 * MetricCard Component
 * Displays real telemetry values and ML inference statistics.
 * Strictly avoids fabricated data: shows "Unavailable" if missing.
 */
export default function MetricCard({
  title,
  value,
  unit = '',
  status,
  subtext,
  source = 'Telemetry Dataset',
  timestamp,
  trend,
  icon
}) {
  const isAvailable = value !== undefined && value !== null && value !== 'Unavailable';

  return (
    <div className="glass-panel interactive-card"
      style={{
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.7) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.18)',
        borderRadius: '10px',
        padding: '16px',
        position: 'relative',
        boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        minHeight: '125px'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {icon && <span style={{ color: '#38bdf8', fontSize: '18px' }}>{icon}</span>}
          <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            {title}
          </span>
        </div>
        {status && <StatusBadge status={status} size="sm" />}
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', margin: '4px 0' }}>
        <span
          style={{
            fontSize: isAvailable ? '24px' : '16px',
            fontWeight: 700,
            color: isAvailable ? '#f8fafc' : '#64748b',
            letterSpacing: '-0.02em',
            fontFamily: 'monospace'
          }}
        >
          {isAvailable ? value : 'Unavailable'}
        </span>
        {isAvailable && unit && (
          <span style={{ fontSize: '13px', fontWeight: 500, color: '#38bdf8' }}>
            {unit}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', fontSize: '11px', color: '#64748b' }}>
        <div>{subtext || (source ? `Src: ${source}` : '')}</div>
        {timestamp && <div>{timestamp}</div>}
      </div>
    </div>
  );
}