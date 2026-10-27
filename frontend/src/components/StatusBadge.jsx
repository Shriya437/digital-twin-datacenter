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
      case 'OBSERVED':
        return {
          bg: 'rgba(6, 182, 212, 0.15)',
          text: '#22d3ee',
          border: '1px solid rgba(34, 211, 238, 0.35)',
          dot: '#06b6d4',
          glow: '0 0 6px rgba(6, 182, 212, 0.4)'
        };
      case 'SIMULATED':
      case 'SYNTHETIC':
        return {
          bg: 'rgba(139, 92, 246, 0.15)',
          text: '#a78bfa',
          border: '1px solid rgba(167, 139, 250, 0.35)',
          dot: '#8b5cf6',
          glow: '0 0 6px rgba(139, 92, 246, 0.4)'
        };
      case 'THERMAL_ANOMALY':
      case 'THERMAL':
        return {
          bg: 'rgba(249, 115, 22, 0.15)',
          text: '#fb923c',
          border: '1px solid rgba(251, 146, 60, 0.4)',
          dot: '#f97316',
          glow: '0 0 8px rgba(249, 115, 22, 0.5)'
        };
      case 'FAN_PERFORMANCE_ANOMALY':
      case 'FAN_ANOMALY':
      case 'FAN':
        return {
          bg: 'rgba(234, 179, 8, 0.15)',
          text: '#facc15',
          border: '1px solid rgba(250, 204, 21, 0.4)',
          dot: '#eab308',
          glow: '0 0 8px rgba(234, 179, 8, 0.5)'
        };
      case 'POWER_ANOMALY':
      case 'POWER':
        return {
          bg: 'rgba(168, 85, 247, 0.15)',
          text: '#c084fc',
          border: '1px solid rgba(192, 132, 252, 0.4)',
          dot: '#a855f7',
          glow: '0 0 8px rgba(168, 85, 247, 0.5)'
        };
      case 'COMBINED_ANOMALY':
      case 'COMBINED':
        return {
          bg: 'rgba(244, 63, 94, 0.18)',
          text: '#fb7185',
          border: '1px solid rgba(251, 113, 133, 0.45)',
          dot: '#f43f5e',
          glow: '0 0 10px rgba(244, 63, 94, 0.6)'
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