import React, { useState, useEffect } from 'react';
import {
  GitFork,
  Search,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ShieldAlert,
  Layers,
  Info,
  Sliders,
  Cpu,
  Wind,
  Zap,
  Server
} from 'lucide-react';
import { api } from '../api/endpoints';

export default function RootCauseView() {
  const [rootCauses, setRootCauses] = useState([]);
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [correlations, setCorrelations] = useState({ matrix: [], interpretation: [] });
  const [selectedCause, setSelectedCause] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [rcRes, graphRes, corrRes] = await Promise.all([
          api.getRootCauses(50),
          api.getDependencyGraph(),
          api.getCorrelations()
        ]);
        setRootCauses(rcRes.data);
        if (rcRes.data?.length > 0) setSelectedCause(rcRes.data[0]);
        setGraphData(graphRes.data);
        setCorrelations(corrRes.data);
      } catch (err) {
        console.error('Failed to load root cause diagnostics:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Compute node positions on circle / grid for SVG interactive rendering
  const nodes = graphData.nodes || [];
  const edges = graphData.edges || [];

  const width = 640;
  const height = 480;
  const centerX = width / 2;
  const centerY = height / 2;

  const nodePositions = {};
  nodes.forEach((n, idx) => {
    if (n.id === 'M100_NODE_1') {
      nodePositions[n.id] = { x: centerX, y: centerY };
    } else {
      const angle = (idx / (nodes.length - 1)) * 2 * Math.PI;
      const radius = 175;
      nodePositions[n.id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      };
    }
  });

  const isAssetAffected = (assetId) => {
    if (!selectedCause) return false;
    return selectedCause.affected_assets?.some(a => a.includes(assetId) || assetId.includes(a));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div className="section-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="badge badge-cyan">Module 3</span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Cross-Layer Anomaly Diagnosis</span>
          </div>
          <h1 className="section-title">Root-Cause Diagnosis & Topology Graph</h1>
          <p className="section-subtitle">
            Ranked list of probable causes beside an interactive infrastructure dependency graph, evidence, affected assets, and diagnostic confidence.
          </p>
        </div>
      </div>

      {/* Main Split: Left = Ranked Causes List, Right = Dependency Graph */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Left Column: Ranked List of Root Causes */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <GitFork size={18} color="var(--cyan-primary)" />
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Ranked Root-Cause Hypotheses</h3>
            </div>
            <span className="badge badge-cyan">{rootCauses.length} Candidate Causes</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '580px', overflowY: 'auto', paddingRight: '4px' }}>
            {rootCauses.map((cause, i) => {
              const isSelected = selectedCause === cause;
              return (
                <div
                  key={i}
                  onClick={() => setSelectedCause(cause)}
                  style={{
                    background: isSelected ? 'rgba(0, 242, 254, 0.08)' : 'var(--bg-surface)',
                    border: isSelected ? '1px solid var(--cyan-primary)' : '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: isSelected ? '0 0 15px rgba(0, 242, 254, 0.15)' : 'none'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: 'rgba(255, 255, 255, 0.05)',
                        border: '1px solid var(--border-card)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        color: 'var(--cyan-primary)'
                      }}>
                        #{i + 1}
                      </span>
                      <strong style={{ fontSize: '0.9rem', color: '#fff' }}>{cause.candidate_cause}</strong>
                    </div>

                    <span className={cause.diagnostic_confidence === 'HIGH' ? 'badge badge-critical' : 'badge badge-warning'}>
                      {cause.diagnostic_confidence} CONFIDENCE
                    </span>
                  </div>

                  {/* Confidence Bar */}
                  <div style={{ marginBottom: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '3px' }}>
                      <span>Diagnostic Ranking Score</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan-primary)', fontWeight: 600 }}>
                        {cause.ranking_score} ({cause.confidence_pct}%)
                      </span>
                    </div>
                    <div style={{ height: '5px', background: 'rgba(255, 255, 255, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div style={{
                        width: `${cause.confidence_pct}%`,
                        height: '100%',
                        background: cause.diagnostic_confidence === 'HIGH' ? 'var(--rose-primary)' : 'var(--amber-primary)',
                        borderRadius: '3px'
                      }} />
                    </div>
                  </div>

                  {/* Evidence Text */}
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.4, marginBottom: '10px' }}>
                    <strong>Evidence:</strong> {cause.evidence}
                  </p>

                  {/* Affected Assets Badges */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Affected Assets:</span>
                    {cause.affected_assets?.map((a, j) => (
                      <span key={j} className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>
                        {a.replace('M100_NODE_1::', '')}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Infrastructure Dependency Graph */}
        <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="var(--cyan-primary)" />
              <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Infrastructure Dependency Graph</h3>
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              11 Nodes • 10 Logical Edges
            </span>
          </div>

          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Reachable logical telemetry associations. Nodes in highlighted red/cyan are implicated in the active root-cause hypothesis.
          </p>

          {/* SVG Graph Visualizer */}
          <div style={{
            background: '#070a10',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '10px',
            position: 'relative'
          }}>
            <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: '390px' }}>
              <defs>
                <marker
                  id="arrow"
                  viewBox="0 0 10 10"
                  refX="18"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255, 255, 255, 0.25)" />
                </marker>
              </defs>

              {/* Render Edges */}
              {edges.map((e, idx) => {
                const src = nodePositions[e.source];
                const tgt = nodePositions[e.target];
                if (!src || !tgt) return null;

                const isEdgeHighlighted = isAssetAffected(e.target);

                return (
                  <line
                    key={idx}
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke={isEdgeHighlighted ? 'var(--cyan-primary)' : 'rgba(255, 255, 255, 0.15)'}
                    strokeWidth={isEdgeHighlighted ? '2.5' : '1.2'}
                    strokeDasharray={isEdgeHighlighted ? '4 2' : 'none'}
                    markerEnd="url(#arrow)"
                  />
                );
              })}

              {/* Render Nodes */}
              {nodes.map((n) => {
                const pos = nodePositions[n.id];
                if (!pos) return null;

                const isHighlighted = isAssetAffected(n.id);
                const isSelected = selectedNode?.id === n.id;
                const isCenter = n.id === 'M100_NODE_1';

                return (
                  <g
                    key={n.id}
                    onClick={() => setSelectedNode(n)}
                    style={{ cursor: 'pointer' }}
                  >
                    {/* Outer glow circle if affected */}
                    {isHighlighted && (
                      <circle
                        cx={pos.x}
                        cy={pos.y}
                        r={isCenter ? 26 : 20}
                        fill="none"
                        stroke="var(--cyan-primary)"
                        strokeWidth="2"
                        opacity="0.8"
                      />
                    )}

                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={isCenter ? 20 : 15}
                      fill={isCenter ? '#0f172a' : (isHighlighted ? 'rgba(0, 242, 254, 0.2)' : '#1e293b')}
                      stroke={isHighlighted ? 'var(--cyan-primary)' : n.color || '#94a3b8'}
                      strokeWidth={isSelected ? '3' : '1.5'}
                    />

                    {/* Node label */}
                    <text
                      x={pos.x}
                      y={pos.y + (isCenter ? 32 : 24)}
                      textAnchor="middle"
                      fill={isHighlighted ? 'var(--cyan-primary)' : 'var(--text-secondary)'}
                      fontSize={isCenter ? '11' : '9.5'}
                      fontWeight={isHighlighted ? '700' : '500'}
                      fontFamily="var(--font-mono)"
                    >
                      {n.label.replace('M100_NODE_1::', '')}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Node detail drawer */}
          {selectedNode && (
            <div style={{ background: 'var(--bg-surface)', padding: '12px 16px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-card)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <strong style={{ fontSize: '0.85rem', color: '#fff' }}>{selectedNode.label}</strong>
                <span className="badge badge-cyan">{selectedNode.category}</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {selectedNode.description || 'Logical dataset-backed telemetry entity.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Sensor Spearman Correlations & Physical Interpretation */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Info size={18} color="var(--cyan-primary)" />
          <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Cross-Metric Correlation & Physical Coupling</h3>
        </div>

        <div className="data-table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Metric Pair</th>
                <th>Spearman Rho (ρ)</th>
                <th>Strength</th>
                <th>Direction</th>
                <th>Domain Physical Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {correlations.interpretation?.map((row, i) => (
                <tr key={i}>
                  <td><strong style={{ color: 'var(--text-primary)' }}>{row.metric_pair}</strong></td>
                  <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan-primary)', fontWeight: 600 }}>
                    {row.spearman_rho}
                  </td>
                  <td>
                    <span className={row.strength === 'STRONG' ? 'badge badge-nominal' : 'badge badge-warning'}>
                      {row.strength}
                    </span>
                  </td>
                  <td>{row.direction}</td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {row.physical_interpretation}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
