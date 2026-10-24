import React, { useMemo } from 'react';

/**
 * TwinTooltip Component
 * Billboarded 2D screen overlay following cursor movement during 3D hover interactions.
 * Displays component identification, live Marconi-100 telemetry, and ML anomaly statuses.
 */
export default function TwinTooltip({ hoveredComponent, pointerCoords }) {
  if (!hoveredComponent) return null;

  const {
    id = 'm100-node1',
    type = 'Compute Server',
    rackId,
    uPosition,
    isMonitored = false,
    status = 'NORMAL',
    telemetry = {}
  } = hoveredComponent;

  // Calculate tooltip screen position with offset to prevent cursor overlap
  const positionStyle = useMemo(() => {
    const offsetX = 18;
    const offsetY = 18;
    const x = (pointerCoords?.x || 0) + offsetX;
    const y = (pointerCoords?.y || 0) + offsetY;

    // Viewport boundary guard
    const isNearRightEdge = typeof window !== 'undefined' && x + 240 > window.innerWidth;
    const isNearBottomEdge = typeof window !== 'undefined' && y + 180 > window.innerHeight;

    return {
      left: isNearRightEdge ? `${x - 260}px` : `${x}px`,
      top: isNearBottomEdge ? `${y - 140}px` : `${y}px`
    };
  }, [pointerCoords]);

  // Status badge styling
  const statusBadgeStyle = useMemo(() => {
    switch (status) {
      case 'ANOMALOUS':
      case 'CRITICAL':
        return {
          bg: 'rgba(239, 68, 68, 0.2)',
          text: '#f87171',
          border: '1px solid rgba(248, 113, 113, 0.4)'
        };
      case 'WARNING':
      case 'ELEVATED':
        return {
          bg: 'rgba(245, 158, 11, 0.2)',
          text: '#fbbf24',
          border: '1px solid rgba(251, 191, 36, 0.4)'
        };
      case 'NORMAL':
        return {
          bg: 'rgba(16, 185, 129, 0.2)',
          text: '#34d399',
          border: '1px solid rgba(52, 211, 153, 0.4)'
        };
      default:
        return {
          bg: 'rgba(100, 116, 139, 0.2)',
          text: '#94a3b8',
          border: '1px solid rgba(148, 163, 184, 0.3)'
        };
    }
  }, [status]);

  return (
    <div
      style={{
        position: 'fixed',
        ...positionStyle,
        width: '240px',
        backgroundColor: 'rgba(11, 19, 43, 0.94)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        borderRadius: '8px',
        padding: '12px 14px',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.6), 0 0 12px rgba(56, 189, 248, 0.15)',
        pointerEvents: 'none',
        zIndex: 100,
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
      }}
    >
      {/* Component Title & Status Badge */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
        <div>
          <div style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc', fontFamily: 'monospace' }}>
            {id}
          </div>
          <div style={{ fontSize: '11px', color: '#38bdf8' }}>{type}</div>
        </div>

        <span
          style={{
            fontSize: '9px',
            fontWeight: 700,
            padding: '2px 6px',
            borderRadius: '4px',
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            backgroundColor: statusBadgeStyle.bg,
            color: statusBadgeStyle.text,
            border: statusBadgeStyle.border
          }}
        >
          {status}
        </span>
      </div>

      {/* Rack & Slot Locational Information */}
      {(rackId || uPosition) && (
        <div style={{ fontSize: '10px', color: '#64748b', marginBottom: '8px', borderBottom: '1px solid rgba(51, 65, 85, 0.4)', paddingBottom: '4px' }}>
          {rackId && <span>{rackId}</span>}
          {rackId && uPosition && <span> • </span>}
          {uPosition && <span>Slot: {uPosition}</span>}
        </div>
      )}

      {/* Live Recorded Telemetry Readings */}
      {isMonitored ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '11px' }}>
          {telemetry?.temp && (
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1' }}>
              <span>Core Temp:</span>
              <strong style={{ color: '#f8fafc', fontFamily: 'monospace' }}>{telemetry.temp}</strong>
            </div>
          )}
          {telemetry?.power && (
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1' }}>
              <span>Power Draw:</span>
              <strong style={{ color: '#f8fafc', fontFamily: 'monospace' }}>{telemetry.power}</strong>
            </div>
          )}
          {telemetry?.fanSpeed && (
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1' }}>
              <span>Fan Speed:</span>
              <strong style={{ color: '#f8fafc', fontFamily: 'monospace' }}>{telemetry.fanSpeed}</strong>
            </div>
          )}
          {telemetry?.statusText && (
            <div style={{ marginTop: '4px', fontSize: '10px', color: status === 'ANOMALOUS' ? '#f87171' : '#34d399' }}>
              ● {telemetry.statusText}
            </div>
          )}
        </div>
      ) : (
        <div style={{ fontSize: '11px', color: '#64748b', fontStyle: 'italic', lineHeight: 1.4 }}>
          {telemetry?.statusText || 'Baseline Cluster Node'}
        </div>
      )}

      {/* Action Cue */}
      <div style={{ marginTop: '8px', paddingTop: '6px', borderTop: '1px solid rgba(51, 65, 85, 0.4)', fontSize: '9px', color: '#00f2fe', textAlign: 'right' }}>
        Click to inspect detailed telemetry ➔
      </div>
    </div>
  );
}