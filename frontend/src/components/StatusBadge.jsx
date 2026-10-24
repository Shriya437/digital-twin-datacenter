import React from 'react';

/**
 * StatusBadge Component
 * Displays model-derived or threshold-derived states:
 * 'HEALTHY' | 'ANOMALOUS' | 'WARNING' | 'CRITICAL' | 'OPTIMAL' | 'UNAVAILABLE'
 */
export default function StatusBadge({ status, label, size = 'sm' }) {
  const normStatus = (status || 'UNKNOWN').toUpperCase();

  const getBadgeStyle = () => {
    switch (normStatus) {
      case 'NORMAL':
      case 'HEALTHY':
      case 'OPTIMAL':
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          text: '#34d399',
          border: '1px solid rgba(52, 211, 153, 0.35)',
          dot: '#10b981',
          glow: '0 0 8px rgba(16, 185, 129, 0.5)'
        };
      case 'WARNING':
      case 'ELEVATED':
      case 'MAINTENANCE_DUE':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          text: '#fbbf24',
          border: '1px solid rgba(251, 191, 36, 0.35)',
          dot: '#f59e0b',
          glow: '0 0 8px rgba(245, 158, 11, 0.5)'
        };
      case 'ANOMALY':
      case 'ANOMALOUS':
      case 'CRITICAL':
      case 'HIGH_RISK':
        return {
          bg: 'rgba(239, 68, 68, 0.15)',
          text: '#f87171',
          border: '1px solid rgba(248, 113, 113, 0.35)',
          dot: '#ef4444',
          glow: '0 0 10px rgba(239, 68, 68, 0.6)'
        };
      case 'UNAVAILABLE':
      case 'NOT AVAILABLE':
      default:
        return {
          bg: 'rgba(100, 116, 139, 0.15)',
          text: '#94a3b8',
          border: '1px solid rgba(148, 163, 184, 0.25)',
          dot: '#64748b',
          glow: 'none'
        };
    }
  };

  const style = getBadgeStyle();
  const isSmall = size === 'sm';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: isSmall ? '2px 8px' : '4px 12px',
        borderRadius: '9999px',
        fontSize: isSmall ? '11px' : '12px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        backgroundColor: style.bg,
        color: style.text,
        border: style.border,
        boxShadow: style.glow !== 'none' ? style.glow : 'none'
      }}
    >
      <span
        style={{
          width: isSmall ? '6px' : '8px',
          height: isSmall ? '6px' : '8px',
          borderRadius: '50%',
          backgroundColor: style.dot,
          boxShadow: `0 0 6px ${style.dot}`
        }}
      />
      {label || normStatus}
    </span>
  );
}