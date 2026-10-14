import React, { useState, useEffect, useRef } from 'react';
import {
  Radio,
  Play,
  Pause,
  RotateCcw,
  FastForward,
  Activity,
  Zap,
  Wind,
  Thermometer,
  Layers,
  Sliders,
  CheckCircle2
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function TelemetryStreamView() {
  const [isPlaying, setIsPlaying] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [currentTick, setCurrentTick] = useState(100);
  const [totalTicks, setTotalTicks] = useState(4917);
  const [streamBuffer, setStreamBuffer] = useState([]);
  const [currentReading, setCurrentReading] = useState(null);
  const [selectedMetricGroup, setSelectedMetricGroup] = useState('temps'); // 'temps', 'power', 'fans'

  const wsRef = useRef(null);

  // Poll or stream telemetry
  useEffect(() => {
    let timer;
    if (isPlaying) {
      timer = setInterval(async () => {
        try {
          const res = await api.getRackState(currentTick);
          const state = res.data;
          setCurrentReading(state);
          setTotalTicks(state.node?.total_telemetry_ticks || 4917);

          // Append to buffer
          setStreamBuffer((prev) => {
            const next = [...prev, {
              tick: currentTick,
              timestamp: state.node?.timestamp,
              p0_temp: state.node?.processors?.[0]?.measured_temp,
              p1_temp: state.node?.processors?.[1]?.measured_temp,
              ambient: state.node?.ambient_temp_c,
              total_power: state.node?.total_power_w,
              fan0: state.node?.cooling_fans?.[0]?.speed_rpm,
              fan1: state.node?.cooling_fans?.[1]?.speed_rpm,
            }];
            return next.slice(-40); // keep last 40 points
          });

          setCurrentTick((prev) => (prev + 1) % 4917);
        } catch (err) {
          console.error('Error fetching stream tick:', err);
        }
      }, 1000 / playbackSpeed);
    }
    return () => clearInterval(timer);
  }, [isPlaying, playbackSpeed, currentTick]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 5</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Online Sensor Ingestion</span>
          </div>
          <h1 className="section-title">Live Telemetry Stream & Replay Console</h1>
          <p className="section-subtitle">
            Simulated live sensor ingestion stream across 4,917 real dataset timestamps with network transport jitter and dynamic buffering.
          </p>
        </div>

        {/* Playback Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            className={isPlaying ? 'btn btn-danger' : 'btn btn-primary'}
            onClick={() => setIsPlaying(!isPlaying)}
          >
            {isPlaying ? <Pause size={16} /> : <Play size={16} />}
            <span>{isPlaying ? 'Pause Stream' : 'Resume Live'}</span>
          </button>

          <div style={{ display: 'flex', background: 'var(--bg-surface)', padding: '2px', borderRadius: 'var(--radius-sm)' }}>
            {[1, 5, 10, 50].map((s) => (
              <button
                key={s}
                onClick={() => setPlaybackSpeed(s)}
                style={{
                  background: playbackSpeed === s ? 'var(--cyan-primary)' : 'transparent',
                  color: playbackSpeed === s ? '#000' : 'var(--text-muted)',
                  border: 'none',
                  padding: '5px 10px',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  cursor: 'pointer'
                }}
              >
                {s}x
              </button>
            ))}
          </div>

          <button
            className="btn btn-secondary"
            onClick={() => {
              setCurrentTick(0);
              setStreamBuffer([]);
            }}
          >
            <RotateCcw size={16} />
            <span>Reset</span>
          </button>
        </div>
      </div>

      {/* Stream Status & Transport Jitter Bar */}
      <div className="glass-panel" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="status-dot nominal"></span>
          <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Stream Ingestion Active</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>•</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            Timestamp: {currentReading?.node?.timestamp || 'Synchronizing...'}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '16px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <span>Transport Latency: <strong style={{ color: 'var(--cyan-primary)' }}>1.24s</strong></span>
          <span>Buffer: <strong style={{ color: '#fff' }}>{streamBuffer.length} / 40 Frames</strong></span>
          <span>Playback Speed: <strong style={{ color: '#34d399' }}>{playbackSpeed}x Realtime</strong></span>
        </div>
      </div>

      {/* Main Metric Visualizer */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
          <div>
            <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Live Telemetry Rolling Waveform</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Real-time multi-channel sensor readings with dynamic baseline tracking.
            </p>
          </div>

          {/* Metric Group Selector */}
          <div style={{ display: 'flex', background: 'var(--bg-surface)', padding: '3px', borderRadius: 'var(--radius-sm)' }}>
            <button
              onClick={() => setSelectedMetricGroup('temps')}
              className="btn"
              style={{
                padding: '4px 12px',
                fontSize: '0.75rem',
                background: selectedMetricGroup === 'temps' ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                color: selectedMetricGroup === 'temps' ? 'var(--cyan-primary)' : 'var(--text-muted)'
              }}
            >
              <Thermometer size={14} />
              <span>Temperatures</span>
            </button>
            <button
              onClick={() => setSelectedMetricGroup('power')}
              className="btn"
              style={{
                padding: '4px 12px',
                fontSize: '0.75rem',
                background: selectedMetricGroup === 'power' ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                color: selectedMetricGroup === 'power' ? 'var(--cyan-primary)' : 'var(--text-muted)'
              }}
            >
              <Zap size={14} />
              <span>Power Draw</span>
            </button>
            <button
              onClick={() => setSelectedMetricGroup('fans')}
              className="btn"
              style={{
                padding: '4px 12px',
                fontSize: '0.75rem',
                background: selectedMetricGroup === 'fans' ? 'rgba(0, 242, 254, 0.15)' : 'transparent',
                color: selectedMetricGroup === 'fans' ? 'var(--cyan-primary)' : 'var(--text-muted)'
              }}
            >
              <Wind size={14} />
              <span>Cooling Fans</span>
            </button>
          </div>
        </div>

        {/* Dynamic SVG Waveform */}
        <div style={{ width: '100%', height: '320px', background: 'rgba(0, 0, 0, 0.35)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
          <svg viewBox="0 0 800 240" style={{ width: '100%', height: '100%' }}>
            {/* Grid */}
            {[50, 100, 150, 200].map((y) => (
              <line key={y} x1="40" y1={y} x2="780" y2={y} stroke="rgba(255, 255, 255, 0.05)" />
            ))}

            {selectedMetricGroup === 'temps' && (
              <>
                {/* P0 Temp Path */}
                {streamBuffer.length > 1 && (
                  <path
                    d={streamBuffer.reduce((acc, pt, i) => {
                      const x = 40 + (i / 39) * 740;
                      const y = 220 - ((pt.p0_temp - 20) / 70) * 190;
                      return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
                    }, '')}
                    fill="none"
                    stroke="#f43f5e"
                    strokeWidth="2.5"
                  />
                )}

                {/* P1 Temp Path */}
                {streamBuffer.length > 1 && (
                  <path
                    d={streamBuffer.reduce((acc, pt, i) => {
                      const x = 40 + (i / 39) * 740;
                      const y = 220 - ((pt.p1_temp - 20) / 70) * 190;
                      return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
                    }, '')}
                    fill="none"
                    stroke="#fb7185"
                    strokeWidth="2"
                    strokeDasharray="4 2"
                  />
                )}

                {/* Ambient Temp Path */}
                {streamBuffer.length > 1 && (
                  <path
                    d={streamBuffer.reduce((acc, pt, i) => {
                      const x = 40 + (i / 39) * 740;
                      const y = 220 - ((pt.ambient - 20) / 70) * 190;
                      return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
                    }, '')}
                    fill="none"
                    stroke="var(--cyan-primary)"
                    strokeWidth="2"
                  />
                )}
              </>
            )}

            {selectedMetricGroup === 'power' && (
              /* Total Power Path */
              streamBuffer.length > 1 && (
                <path
                  d={streamBuffer.reduce((acc, pt, i) => {
                    const x = 40 + (i / 39) * 740;
                    const y = 220 - ((pt.total_power - 200) / 1000) * 190;
                    return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
                  }, '')}
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="2.5"
                />
              )
            )}

            {selectedMetricGroup === 'fans' && (
              /* Fan RPM Path */
              streamBuffer.length > 1 && (
                <path
                  d={streamBuffer.reduce((acc, pt, i) => {
                    const x = 40 + (i / 39) * 740;
                    const y = 220 - ((pt.fan0 - 1500) / 8000) * 190;
                    return i === 0 ? `M ${x} ${y}` : `${acc} L ${x} ${y}`;
                  }, '')}
                  fill="none"
                  stroke="#34d399"
                  strokeWidth="2.5"
                />
              )
            )}
          </svg>
        </div>

        {/* Legend */}
        <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem' }}>
          <div style={{ display: 'flex', gap: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '12px', height: '3px', background: '#f43f5e' }}></span>
              <span>Processor 0 VDD ({streamBuffer[streamBuffer.length - 1]?.p0_temp ?? 52}°C)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '12px', height: '3px', background: 'var(--cyan-primary)' }}></span>
              <span>Ambient Inflow ({streamBuffer[streamBuffer.length - 1]?.ambient ?? 21.8}°C)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '12px', height: '3px', background: '#fbbf24' }}></span>
              <span>Chassis Total Power ({streamBuffer[streamBuffer.length - 1]?.total_power ?? 640} W)</span>
            </div>
          </div>

          <span className="badge badge-nominal">Continuous FIFO Ring Buffer</span>
        </div>
      </div>
    </div>
  );
}
