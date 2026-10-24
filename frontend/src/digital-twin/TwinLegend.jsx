import React from 'react';

/**
 * TwinLegend Component
 * Displays visual semantics for 3D equipment status, thermal heatmap thresholds,
 * and ML anomaly indicators across active visualization modes.
 */
export default function TwinLegend({ activeMode = 'telemetry' }) {
  return (
    <div
      style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        backgroundColor: 'rgba(11, 19, 43, 0.92)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        borderRadius: '8px',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        zIndex: 20,
        boxShadow: '0 6px 20px rgba(0, 0, 0, 0.6)',
        fontSize: '11px',
        color: '#cbd5e1',
        pointerEvents: 'none',
        maxWidth: '280px',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid rgba(51, 65, 85, 0.5)',
          paddingBottom: '5px'
        }}
      >
        <span
          style={{
            fontSize: '10px',
            fontWeight: 700,
            color: '#64748b',
            textTransform: 'uppercase',
            letterSpacing: '0.06em'
          }}
        >
          Visual State Key
        </span>
        <span
          style={{
            fontSize: '9px',
            fontWeight: 700,
            color: '#38bdf8',
            backgroundColor: 'rgba(14, 165, 233, 0.15)',
            padding: '1px 6px',
            borderRadius: '4px',
            textTransform: 'uppercase'
          }}
        >
          {activeMode}
        </span>
      </div>

      {/* MODE 1: Nominal Telemetry Mode */}
      {activeMode === 'telemetry' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#10b981',
                boxShadow: '0 0 6px #10b981'
              }}
            />
            <span>Nominal In-Spec (&lt; 35°C)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#f59e0b',
                boxShadow: '0 0 6px #f59e0b'
              }}
            />
            <span>Elevated Load / Temp (35–45°C)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#ef4444',
                boxShadow: '0 0 6px #ef4444'
              }}
            />
            <span>Critical Thermal Draw (&gt; 45°C)</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#475569'
              }}
            />
            <span>Baseline Blade (Unmonitored)</span>
          </div>
        </div>
      )}

      {/* MODE 2: Continuous Thermal Gradient Heatmap */}
      {activeMode === 'thermal' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div
            style={{
              height: '8px',
              borderRadius: '4px',
              background: 'linear-gradient(90deg, #00f2fe 0%, #38bdf8 30%, #f59e0b 70%, #ef4444 100%)',
              border: '1px solid rgba(255, 255, 255, 0.15)'
            }}
          />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '10px',
              color: '#94a3b8',
              fontFamily: 'monospace'
            }}
          >
            <span>20°C (Inlet)</span>
            <span>35°C</span>
            <span>75°C+ (Core)</span>
          </div>
          <span style={{ fontSize: '10px', color: '#64748b', fontStyle: 'italic', marginTop: '2px' }}>
            Interpolated surface heatmap driven by temp_core_max
          </span>
        </div>
      )}

      {/* MODE 3: ML Anomaly Detector Mode */}
      {activeMode === 'anomaly' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#ef4444',
                boxShadow: '0 0 8px #ef4444'
              }}
            />
            <span>Isolation Forest Flagged Outlier</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#00f2fe',
                boxShadow: '0 0 6px #00f2fe'
              }}
            />
            <span>In-Distribution Nominal Stream</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '2px',
                border: '1px solid #00f2fe',
                backgroundColor: 'rgba(0, 242, 254, 0.2)'
              }}
            />
            <span>Selected Target Blade Focus</span>
          </div>

          <span style={{ fontSize: '10px', color: '#64748b', fontStyle: 'italic', marginTop: '2px' }}>
            Threshold: Contamination = 0.01 | Score &gt; 0.60
          </span>
        </div>
      )}

      {/* Data Source Footnote */}
      <div
        style={{
          borderTop: '1px solid rgba(51, 65, 85, 0.4)',
          paddingTop: '5px',
          fontSize: '9px',
          color: '#64748b'
        }}
      >
        Source: Marconi-100 Node 1 Stream (RACK-A01)
      </div>
    </div>
  );
}