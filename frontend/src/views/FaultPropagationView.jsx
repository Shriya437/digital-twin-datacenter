import React, { useState, useEffect } from 'react';
import {
  Zap,
  ShieldAlert,
  AlertTriangle,
  Play,
  RotateCcw,
  Layers,
  ChevronRight,
  Flame,
  Wind,
  Cpu,
  Server
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function FaultPropagationView() {
  const [faultType, setFaultType] = useState('FAN_FAILURE');
  const [severity, setSeverity] = useState(1.0);
  const [simulationResult, setSimulationResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    runSimulation();
  }, []);

  async function runSimulation() {
    try {
      setLoading(true);
      const res = await api.simulateFault(faultType, severity);
      setSimulationResult(res.data);
    } catch (err) {
      console.error('Failed to run fault simulation:', err);
    } finally {
      setLoading(false);
    }
  }

  const { cascade_timeline, blast_radius_stages, affected_components_count } = simulationResult || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 6</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Cascading Impact Analysis</span>
          </div>
          <h1 className="section-title">Fault Propagation & Blast Radius</h1>
          <p className="section-subtitle">
            Simulate synthetic fault injection to trace downstream cascading fallout across power, thermal, and workload layers.
          </p>
        </div>
      </div>

      {/* Interactive Fault Injection Control Studio */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Zap size={18} color="var(--rose-primary)" />
          <span>Interactive Fault Injection Studio</span>
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr auto', gap: '20px', alignItems: 'flex-end' }}>
          {/* Fault Type Selector */}
          <div>
            <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
              Injected Anomaly / Failure Scenario
            </label>
            <select
              className="select"
              value={faultType}
              onChange={(e) => setFaultType(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="FAN_FAILURE">Chassis Fan Intake Failure (Fan 0 Stalled)</option>
              <option value="POWER_SURGE">Power Supply Transient Surge (PS0 Load Dump)</option>
              <option value="THERMAL_SPIKE">Socket 0 Thermal Runaway (TIM Delamination)</option>
              <option value="AMBIENT_HEATWAVE">Data Hall CRAH Chiller Failure (+12°C Heatwave)</option>
              <option value="SENSOR_DRIFT">Analog RTD Sensor Offset Bias (+15°C Drift)</option>
            </select>
          </div>

          {/* Severity Slider */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              <span>Fault Severity Magnitude</span>
              <strong style={{ color: 'var(--cyan-primary)' }}>{severity}x</strong>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.0"
              step="0.1"
              value={severity}
              onChange={(e) => setSeverity(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--cyan-primary)' }}
            />
          </div>

          {/* Run Button */}
          <button className="btn btn-primary" onClick={runSimulation} disabled={loading}>
            <Play size={16} />
            <span>{loading ? 'Propagating...' : 'Trigger Simulation'}</span>
          </button>
        </div>
      </div>

      {/* Blast Radius Metrics Summary */}
      <div className="grid-cols-3">
        <div className="glass-panel" style={{ padding: '20px' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Blast Radius Depth</span>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fb7185', fontFamily: 'var(--font-mono)', margin: '8px 0 4px' }}>
            {blast_radius_stages ?? 3} Cascading Stages
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>From Physical Core to Workload</span>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Affected Components</span>
          <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--amber-primary)', fontFamily: 'var(--font-mono)', margin: '8px 0 4px' }}>
            {affected_components_count ?? 5} Subsystems Implicated
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Downstream Failure Vector</span>
        </div>

        <div className="glass-panel" style={{ padding: '20px' }}>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Recommended Mitigation</span>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--cyan-primary)', margin: '8px 0 4px' }}>
            Workload Migration & 15% Power Cap
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Automated Safety Gate Available</span>
        </div>
      </div>

      {/* Cascading Timeline Tree */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '20px' }}>
          Multi-Stage Cascading Propagation Timeline
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative' }}>
          {cascade_timeline?.map((step, idx) => (
            <div
              key={idx}
              style={{
                display: 'grid',
                gridTemplateColumns: '120px 220px 1fr 100px',
                gap: '16px',
                alignItems: 'center',
                background: 'var(--bg-surface)',
                padding: '16px 20px',
                borderRadius: 'var(--radius-md)',
                borderLeft: step.stage === 0 ? '4px solid var(--rose-primary)' : '4px solid var(--amber-primary)',
                border: '1px solid var(--border-subtle)'
              }}
            >
              {/* Stage Badge */}
              <div>
                <span className={step.stage === 0 ? 'badge badge-critical' : 'badge badge-warning'} style={{ fontSize: '0.7rem' }}>
                  {step.stage === 0 ? 'ORIGIN POINT' : `CASCADE STAGE ${step.stage}`}
                </span>
              </div>

              {/* Asset & Type */}
              <div>
                <strong style={{ fontSize: '0.88rem', color: '#fff', display: 'block' }}>{step.asset_id}</strong>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{step.impact_type}</span>
              </div>

              {/* Description */}
              <div>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  {step.description}
                </p>
              </div>

              {/* Status */}
              <div style={{ textAlign: 'right' }}>
                <span className={step.status === 'FAILED' || step.status === 'CRITICAL' ? 'badge badge-critical' : 'badge badge-warning'}>
                  {step.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
