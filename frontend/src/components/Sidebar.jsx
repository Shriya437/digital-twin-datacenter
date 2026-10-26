import React from 'react';
import {
  Activity,
  Server,
  GitFork,
  Wrench,
  Radio,
  Zap,
  BatteryCharging,
  CheckCircle2,
  Shield,
  Layers
} from 'lucide-react';

const MODULES = [
  { id: 'overview', label: '1. Overview Dashboard', icon: Activity, badge: 'Live', group: 'Command' },
  { id: 'twin', label: '2. Digital Twin Rack', icon: Server, badge: '3D/2D', group: 'Simulation' },
  { id: 'root-cause', label: '3. Root-Cause Diagnosis', icon: GitFork, badge: 'ML Graph', group: 'Diagnostics' },
  { id: 'predictive', label: '4. Predictive Maintenance', icon: Wrench, badge: 'Early Warning', group: 'Diagnostics' },
  { id: 'telemetry', label: '5. Telemetry Stream', icon: Radio, badge: '4.9k Ticks', group: 'Telemetry' },
  { id: 'faults', label: '6. Fault Propagation', icon: Zap, badge: 'Blast Radius', group: 'Simulation' },
  { id: 'energy', label: '7. Energy & What-If', icon: BatteryCharging, badge: 'kWh & PUE', group: 'Analytics' },
  { id: 'reliability', label: '8. Sensor Reliability', icon: CheckCircle2, badge: 'Quality', group: 'Telemetry' },
  { id: 'decision', label: '9. Decision Support & Audit', icon: Shield, badge: 'Gate', group: 'Governance' },
];

export default function Sidebar({ currentModule, onSelectModule }) {
  return (
    <aside style={{
      width: '260px',
      background: 'rgba(10, 14, 23, 0.95)',
      borderRight: '1px solid var(--border-card)',
      display: 'flex',
      flexDirection: 'column',
      padding: '16px 12px',
      gap: '24px'
    }}>
      {/* Category header */}
      <div>
        <div style={{
          fontSize: '0.72rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.08em',
          color: 'var(--text-muted)',
          marginBottom: '10px',
          paddingLeft: '10px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px'
        }}>
          <Layers size={14} color="var(--cyan-primary)" />
          <span>9 Integrated Modules</span>
        </div>

        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {MODULES.map((mod) => {
            const Icon = mod.icon;
            const isActive = currentModule === mod.id;

            return (
              <button
                key={mod.id}
                onClick={() => onSelectModule(mod.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  background: isActive
                    ? 'linear-gradient(90deg, rgba(0, 242, 254, 0.15), rgba(0, 242, 254, 0.03))'
                    : 'transparent',
                  border: isActive
                    ? '1px solid rgba(0, 242, 254, 0.4)'
                    : '1px solid transparent',
                  color: isActive ? '#fff' : 'var(--text-secondary)',
                  cursor: 'pointer',
                  textAlign: 'left',
                  transition: 'all 0.18s ease',
                  outline: 'none',
                  width: '100%',
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)';
                    e.currentTarget.style.color = '#fff';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                  }
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Icon
                    size={17}
                    color={isActive ? 'var(--cyan-primary)' : 'var(--text-muted)'}
                  />
                  <span style={{
                    fontSize: '0.82rem',
                    fontWeight: isActive ? 600 : 500,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis'
                  }}>
                    {mod.label}
                  </span>
                </div>

                {mod.badge && (
                  <span style={{
                    fontSize: '0.65rem',
                    fontFamily: 'var(--font-mono)',
                    padding: '2px 5px',
                    borderRadius: '4px',
                    background: isActive ? 'rgba(0, 242, 254, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                    color: isActive ? 'var(--cyan-primary)' : 'var(--text-muted)',
                    border: isActive ? '1px solid rgba(0, 242, 254, 0.3)' : '1px solid var(--border-subtle)'
                  }}>
                    {mod.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Footer Info Box */}
      <div style={{
        marginTop: 'auto',
        background: 'rgba(19, 25, 38, 0.5)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: '12px',
        fontSize: '0.73rem',
        color: 'var(--text-muted)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', color: 'var(--text-secondary)', fontWeight: 600 }}>
          <Server size={13} color="var(--cyan-primary)" />
          <span>CINECA Marconi100</span>
        </div>
        <p>Real telemetry and ML surrogate models connected via FastAPI endpoints.</p>
      </div>
    </aside>
  );
}
