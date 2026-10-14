import React, { useState, useEffect } from 'react';
import { Activity, Server, Radio, Shield, Clock, AlertTriangle } from 'lucide-react';

export default function Header({ activeIncidentsCount = 0, isLive = true }) {
  const [time, setTime] = useState('');

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTime(now.toUTCString().replace('GMT', 'UTC'));
    };
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header style={{
      height: '64px',
      background: 'rgba(13, 17, 26, 0.85)',
      backdropFilter: 'blur(16px)',
      borderBottom: '1px solid var(--border-card)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 24px',
      position: 'sticky',
      top: 0,
      zIndex: 50
    }}>
      {/* Left: Brand & Node Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, rgba(0, 242, 254, 0.2), rgba(79, 172, 254, 0.05))',
          border: '1px solid rgba(0, 242, 254, 0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 15px rgba(0, 242, 254, 0.25)'
        }}>
          <Server size={20} color="var(--cyan-primary)" />
        </div>

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{
              fontWeight: 800,
              fontSize: '1rem',
              letterSpacing: '0.04em',
              background: 'linear-gradient(90deg, #fff, #94a3b8)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent'
            }}>
              DATA CENTER DIGITAL TWIN
            </span>
            <span className="badge badge-cyan" style={{ fontSize: '0.68rem', padding: '2px 6px' }}>
              MARCONI100 TIER-0
            </span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '12px' }}>
            <span>Target: <strong style={{ color: 'var(--text-secondary)' }}>M100_NODE_1</strong></span>
            <span>•</span>
            <span>Chassis: <strong style={{ color: 'var(--text-secondary)' }}>IBM Power AC922 (U19-U20)</strong></span>
          </div>
        </div>
      </div>

      {/* Right: Telemetry Link & Status Indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        {/* Stream Status */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(0, 0, 0, 0.3)',
          padding: '6px 12px',
          borderRadius: '9999px',
          border: '1px solid var(--border-subtle)',
          fontSize: '0.78rem'
        }}>
          <span className="status-dot nominal"></span>
          <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
            BACKEND: <strong style={{ color: '#34d399' }}>FASTAPI ONLINE</strong>
          </span>
        </div>

        {/* Active Incidents Counter */}
        {activeIncidentsCount > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: 'rgba(244, 63, 94, 0.15)',
            border: '1px solid rgba(244, 63, 94, 0.35)',
            padding: '5px 10px',
            borderRadius: '9999px',
            fontSize: '0.75rem',
            color: '#fb7185',
            fontWeight: 600
          }}>
            <AlertTriangle size={14} />
            <span>{activeIncidentsCount} ANOMALIES FLAGGED</span>
          </div>
        )}

        {/* Mission Control UTC Clock */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.78rem',
          color: 'var(--text-secondary)',
          background: 'var(--bg-surface)',
          padding: '6px 12px',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border-subtle)'
        }}>
          <Clock size={14} color="var(--cyan-primary)" />
          <span>{time}</span>
        </div>
      </div>
    </header>
  );
}
