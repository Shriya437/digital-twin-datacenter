import React from 'react';
import StatusBadge from './StatusBadge';

/**
 * Header Component
 * Displays system status, active node from Marconi-100 dataset, connection & freshness.
 */
export default function Header({
  activeDataset = 'm100_node1_digital_twin.csv',
  totalRecords = 17280,
  latestTimestamp = '2026-10-23 18:30:00 UTC',
  backendConnected = true
}) {
  return (
    <header
      style={{
        height: '62px',
        backgroundColor: 'rgba(11, 19, 43, 0.95)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(56, 189, 248, 0.15)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        position: 'sticky',
        top: 0,
        zIndex: 50
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              backgroundColor: '#00f2fe',
              boxShadow: '0 0 10px #00f2fe'
            }}
          />
          <span style={{ fontSize: '15px', fontWeight: 700, color: '#f8fafc', letterSpacing: '0.04em' }}>
            HPC DATA CENTER TWIN
          </span>
        </div>
        <span style={{ color: 'rgba(100, 116, 139, 0.4)' }}>|</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#94a3b8' }}>
          <span>Dataset:</span>
          <span style={{ color: '#38bdf8', fontFamily: 'monospace', fontWeight: 600 }}>{activeDataset}</span>
          <span style={{ color: '#64748b' }}>({totalRecords.toLocaleString()} rows)</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ fontSize: '12px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>Last Observation:</span>
          <span style={{ color: '#f1f5f9', fontFamily: 'monospace' }}>{latestTimestamp}</span>
        </div>
        <StatusBadge
          status={backendConnected ? 'HEALTHY' : 'CRITICAL'}
          label={backendConnected ? 'API SYNCHRONIZED' : 'OFFLINE'}
          size="sm"
        />
      </div>
    </header>
  );
}