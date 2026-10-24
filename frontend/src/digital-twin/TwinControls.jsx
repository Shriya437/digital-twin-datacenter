import React from 'react';

export default function TwinControls({
  activePreset = 'overview',
  onPresetChange,
  activeMode = 'telemetry',
  onModeChange
}) {
  const cameraPresets = [
    { id: 'overview', label: 'Overview', icon: '◰' },
    { id: 'aisle', label: 'Cold Aisle', icon: '⫿' },
    { id: 'topDown', label: 'Top-Down', icon: '⊞' },
    { id: 'focusNode', label: 'Node 1', icon: '◎' }
  ];

  const viewModes = [
    { id: 'telemetry', label: 'Telemetry', icon: '⚡' },
    { id: 'thermal', label: 'Thermal CFD', icon: '♨' },
    { id: 'anomaly', label: 'ML Anomaly', icon: '⚠' }
  ];

  return (
    <div
      style={{
        position: 'absolute',
        top: '16px',
        right: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        zIndex: 20
      }}
    >
      {/* Camera Presets Selector */}
      <div
        style={{
          backgroundColor: 'rgba(8, 20, 48, 0.88)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(0, 242, 254, 0.35)',
          borderRadius: '10px',
          padding: '6px 8px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5), 0 0 10px rgba(0, 242, 254, 0.15)'
        }}
      >
        <span
          style={{
            fontSize: '10px',
            fontWeight: 800,
            color: '#00f2fe',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            padding: '2px 6px',
            display: 'block'
          }}
        >
          Camera Presets
        </span>

        <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
          {cameraPresets.map((preset) => {
            const isActive = activePreset === preset.id;
            return (
              <button
                key={preset.id}
                onClick={() => onPresetChange && onPresetChange(preset.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: isActive ? '1px solid #00f2fe' : '1px solid rgba(255, 255, 255, 0.1)',
                  backgroundColor: isActive ? 'rgba(0, 242, 254, 0.25)' : 'rgba(15, 23, 42, 0.6)',
                  color: isActive ? '#ffffff' : '#94a3b8',
                  fontSize: '11px',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  boxShadow: isActive ? '0 0 10px rgba(0, 242, 254, 0.4)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                <span>{preset.icon}</span>
                <span>{preset.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Visualization Mode Selector */}
      <div
        style={{
          backgroundColor: 'rgba(8, 20, 48, 0.88)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(0, 242, 254, 0.35)',
          borderRadius: '10px',
          padding: '6px 8px',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5), 0 0 10px rgba(0, 242, 254, 0.15)'
        }}
      >
        <span
          style={{
            fontSize: '10px',
            fontWeight: 800,
            color: '#00f2fe',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            padding: '2px 6px',
            display: 'block'
          }}
        >
          Visualization Mode
        </span>

        <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
          {viewModes.map((mode) => {
            const isActive = activeMode === mode.id;
            return (
              <button
                key={mode.id}
                onClick={() => onModeChange && onModeChange(mode.id)}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  border: isActive ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.1)',
                  backgroundColor: isActive ? 'rgba(16, 185, 129, 0.25)' : 'rgba(15, 23, 42, 0.6)',
                  color: isActive ? '#ffffff' : '#94a3b8',
                  fontSize: '11px',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  boxShadow: isActive ? '0 0 10px rgba(16, 185, 129, 0.4)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                <span>{mode.icon}</span>
                <span>{mode.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}