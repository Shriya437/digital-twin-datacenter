import React from 'react';

/**
 * ChartPanel Component
 * Lightweight, zero-dependency SVG chart for time-series, forecasts, and anomaly spans.
 * Strictly separates Historical Telemetry (cyan) vs Predictions (orange dashed).
 */
export default function ChartPanel({
  title,
  historicalData = [],
  forecastData = [],
  xKey = 'timestamp',
  yKey = 'value',
  unit = '',
  anomalies = [],
  height = 220
}) {
  const allValues = [
    ...historicalData.map((d) => d[yKey]),
    ...forecastData.map((d) => d[yKey])
  ].filter((v) => typeof v === 'number' && !isNaN(v));

  if (allValues.length === 0) {
    return (
      <div className="glass-panel"
        style={{
          background: 'rgba(15, 23, 42, 0.75)',
          border: '1px solid rgba(56, 189, 248, 0.15)',
          borderRadius: '10px',
          padding: '18px',
          height: `${height}px`,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#64748b',
          fontSize: '13px'
        }}
      >
        <span style={{ marginBottom: '6px', fontWeight: 600, color: '#94a3b8' }}>{title}</span>
        <span>Telemetry data currently unavailable for plotting</span>
      </div>
    );
  }

  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const range = maxVal - minVal || 1;
  const padding = 35;
  const chartHeight = height - 55;
  const width = 600;

  const totalPoints = historicalData.length + forecastData.length;
  const stepX = (width - padding * 2) / Math.max(totalPoints - 1, 1);

  // Helper to map index & value to SVG coordinate space
  const getCoords = (idx, val) => {
    const x = padding + idx * stepX;
    const y = chartHeight - padding - ((val - minVal) / range) * (chartHeight - padding * 2);
    return { x, y };
  };

  // Build SVG path for historical points
  let histPath = '';
  historicalData.forEach((d, i) => {
    const pt = getCoords(i, d[yKey]);
    histPath += `${i === 0 ? 'M' : 'L'} ${pt.x} ${pt.y} `;
  });

  // Build SVG path for forecasted points
  let forecastPath = '';
  if (historicalData.length > 0 && forecastData.length > 0) {
    const lastHist = getCoords(historicalData.length - 1, historicalData[historicalData.length - 1][yKey]);
    forecastPath = `M ${lastHist.x} ${lastHist.y} `;
  }
  forecastData.forEach((d, i) => {
    const pt = getCoords(historicalData.length + i, d[yKey]);
    forecastPath += `${forecastPath === '' ? 'M' : 'L'} ${pt.x} ${pt.y} `;
  });

  return (
    <div className="glass-panel"
      style={{
        background: 'rgba(15, 23, 42, 0.85)',
        border: '1px solid rgba(56, 189, 248, 0.18)',
        borderRadius: '10px',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#cbd5e1', letterSpacing: '0.03em' }}>{title}</span>
        <div style={{ display: 'flex', gap: '14px', fontSize: '11px', color: '#94a3b8' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '10px', height: '2px', backgroundColor: '#38bdf8' }} /> Telemetry
          </span>
          {forecastData.length > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ width: '10px', height: '2px', backgroundColor: '#f97316', borderTop: '1px dashed #f97316' }} /> ML Forecast
            </span>
          )}
        </div>
      </div>

      <svg viewBox={`0 0 ${width} ${chartHeight}`} style={{ width: '100%', height: `${chartHeight}px` }}>
        {/* Horizontal grid lines */}
        {[0, 0.33, 0.66, 1].map((pct, idx) => {
          const yPos = chartHeight - padding - pct * (chartHeight - padding * 2);
          const gridVal = (minVal + pct * range).toFixed(1);
          return (
            <g key={idx}>
              <line x1={padding} y1={yPos} x2={width - padding} y2={yPos} stroke="rgba(51, 65, 85, 0.4)" strokeDasharray="3 3" />
              <text x={padding - 6} y={yPos + 4} fill="#64748b" fontSize="10" textAnchor="end" fontFamily="monospace">
                {gridVal}
                {unit}
              </text>
            </g>
          );
        })}

        {/* Historical line */}
        {histPath && <path d={histPath} fill="none" stroke="#38bdf8" strokeWidth="2.2" strokeLinecap="round" />}

        {/* Forecast line */}
        {forecastPath && (
          <path d={forecastPath} fill="none" stroke="#f97316" strokeWidth="2.2" strokeDasharray="4 4" strokeLinecap="round" />
        )}

        {/* Render Anomaly Flag points */}
        {historicalData.map((d, i) => {
          if (anomalies.includes(i) || d.is_anomaly) {
            const pt = getCoords(i, d[yKey]);
            return (
              <circle
                key={`anom-${i}`}
                cx={pt.x}
                cy={pt.y}
                r="4.5"
                fill="#ef4444"
                stroke="#ffffff"
                strokeWidth="1.5"
              />
            );
          }
          return null;
        })}
      </svg>
    </div>
  );
}