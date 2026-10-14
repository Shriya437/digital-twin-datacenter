import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Lock,
  UserCheck,
  FileText,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Clock
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function DecisionSupportView() {
  const [auditLogs, setAuditLogs] = useState([]);
  const [operator, setOperator] = useState('Elena Rostova');
  const [role, setRole] = useState('lead_engineer');
  const [action, setAction] = useState('FAN_DUTY_CYCLE_OVERRIDE');
  const [targetAsset, setTargetAsset] = useState('M100_NODE_1::fan0_0');
  const [riskScore, setRiskScore] = useState(0.28);
  const [uncertaintyScore, setUncertaintyScore] = useState(0.12);
  const [validationResult, setValidationResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadAudit();
  }, []);

  async function loadAudit() {
    try {
      const res = await api.getAuditLogs();
      setAuditLogs(res.data);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
    }
  }

  async function handleValidate(e) {
    e.preventDefault();
    try {
      setLoading(true);
      const res = await api.validateDecisionAction({
        action,
        target_asset: targetAsset,
        operator,
        role,
        risk_score: Number(riskScore),
        uncertainty_score: Number(uncertaintyScore),
        parameters: { simulated_timestamp: new Date().toISOString() }
      });
      setValidationResult(res.data);
      loadAudit();
    } catch (err) {
      console.error('Failed to validate action:', err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 9</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Safety Gates & Governance</span>
          </div>
          <h1 className="section-title">Decision Support & Security Audit</h1>
          <p className="section-subtitle">
            Safety gate enforcement, role-based access control, automated uncertainty verification, and immutable audit logging.
          </p>
        </div>
      </div>

      {/* Split: Left = Action Validation Tester, Right = Safety Gate Criteria */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '24px' }}>
        {/* Action Testing Form */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Shield size={18} color="var(--cyan-primary)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Safety Gate Action Validation</h3>
          </div>

          <form onSubmit={handleValidate} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Operator Name
                </label>
                <input
                  type="text"
                  className="input"
                  value={operator}
                  onChange={(e) => setOperator(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Authorized Role
                </label>
                <select
                  className="select"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  style={{ width: '100%' }}
                >
                  <option value="lead_engineer">Lead Systems Engineer</option>
                  <option value="operator">Operations Technician</option>
                  <option value="system_admin">System Administrator</option>
                  <option value="facility_director">Facility Director</option>
                  <option value="ai_agent">Twin Autonomous Agent</option>
                  <option value="unauthorized_guest">Unauthorized Guest (Test Block)</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Action Payload
                </label>
                <select
                  className="select"
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  style={{ width: '100%' }}
                >
                  <option value="FAN_DUTY_CYCLE_OVERRIDE">FAN_DUTY_CYCLE_OVERRIDE (PWM 95%)</option>
                  <option value="APPLY_POWER_CAP_15_PCT">APPLY_POWER_CAP_15_PCT (Cap to 542W)</option>
                  <option value="DVFS_FREQUENCY_THROTTLE">DVFS_FREQUENCY_THROTTLE (Throttle to 2.8GHz)</option>
                  <option value="ISOLATE_CHASSIS_BLADE">ISOLATE_CHASSIS_BLADE (Emergency Isolation)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Target Component Asset ID
                </label>
                <input
                  type="text"
                  className="input"
                  value={targetAsset}
                  onChange={(e) => setTargetAsset(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  <span>Assessed Action Risk</span>
                  <strong style={{ color: riskScore > 0.5 ? '#fb7185' : 'var(--cyan-primary)' }}>{riskScore}</strong>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={riskScore}
                  onChange={(e) => setRiskScore(e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--cyan-primary)' }}
                />
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  <span>Model Uncertainty Margin</span>
                  <strong style={{ color: uncertaintyScore > 0.25 ? '#fb7185' : 'var(--cyan-primary)' }}>{uncertaintyScore}</strong>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="0.5"
                  step="0.02"
                  value={uncertaintyScore}
                  onChange={(e) => setUncertaintyScore(e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--cyan-primary)' }}
                />
              </div>
            </div>

            <button type="submit" className="btn btn-primary" style={{ alignSelf: 'flex-start', marginTop: '4px' }} disabled={loading}>
              <ShieldCheck size={16} />
              <span>{loading ? 'Evaluating...' : 'Validate Action via Safety Gate'}</span>
            </button>
          </form>

          {/* Validation Result Box */}
          {validationResult && (
            <div style={{
              marginTop: '20px',
              padding: '16px',
              borderRadius: 'var(--radius-md)',
              background: validationResult.gate_passed ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
              border: validationResult.gate_passed ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(244, 63, 94, 0.3)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {validationResult.gate_passed ? (
                  <CheckCircle2 size={18} color="#34d399" />
                ) : (
                  <AlertTriangle size={18} color="#fb7185" />
                )}
                <strong style={{ fontSize: '0.9rem', color: validationResult.gate_passed ? '#34d399' : '#fb7185' }}>
                  {validationResult.gate_passed ? 'SAFETY GATE APPROVED: Action logged to audit trail' : 'SAFETY GATE BLOCKED: Safety constraints violated'}
                </strong>
              </div>

              {!validationResult.gate_passed && validationResult.rejection_reasons?.length > 0 && (
                <ul style={{ margin: '8px 0 0 24px', fontSize: '0.78rem', color: '#fb7185' }}>
                  {validationResult.rejection_reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>

        {/* Safety Gate Threshold Rules */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Lock size={18} color="var(--amber-primary)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Active Safety Criteria</h3>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '12px 14px', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>MAXIMUM RISK CEILING</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--amber-primary)', fontFamily: 'var(--font-mono)' }}>0.50 Max</div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Actions with projected risk &gt;0.50 are blocked from execution on production node.
            </p>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '12px 14px', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>UNCERTAINTY TOLERANCE</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--cyan-primary)', fontFamily: 'var(--font-mono)' }}>0.25 Max</div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Surrogate ML model predictions with variance &gt;0.25 require human sign-off.
            </p>
          </div>

          <div style={{ background: 'var(--bg-surface)', padding: '12px 14px', borderRadius: 'var(--radius-sm)' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>DATA HEALTH CONTRACT</span>
            <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#34d399', fontFamily: 'var(--font-mono)' }}>&ge;99.0% Valid</div>
            <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Minimum valid timestamp fraction and &le;5% missing metric row threshold.
            </p>
          </div>
        </div>
      </div>

      {/* Immutable Audit Log Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="var(--cyan-primary)" />
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Immutable Action Audit Trail</h3>
          </div>
          <span className="badge badge-nominal">{auditLogs.length} Records</span>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Audit ID</th>
                <th>Timestamp (UTC)</th>
                <th>Operator</th>
                <th>Role</th>
                <th>Action</th>
                <th>Target Asset</th>
                <th>Gate Verdict</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id}>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan-primary)', fontWeight: 600 }}>{log.id}</td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>{log.timestamp}</td>
                  <td><strong>{log.operator}</strong></td>
                  <td><span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>{log.role}</span></td>
                  <td><code style={{ fontFamily: 'var(--font-mono)', color: '#fff' }}>{log.action}</code></td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>{log.target_asset}</td>
                  <td>
                    {log.safety_gate_passed ? (
                      <span className="badge badge-nominal">APPROVED</span>
                    ) : (
                      <span className="badge badge-critical">BLOCKED</span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{log.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
