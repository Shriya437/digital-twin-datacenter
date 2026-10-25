import React, { useState } from 'react';

/**
 * ChartPanel Component
 * High-fidelity, zero-dependency SVG chart for digital twin telemetry, ML forecasts, and anomalies.
 * 
 * Features:
 * 1. Dual Mode: Supports both Same-Timeline Comparison (Actual vs Predicted) and Sequential Horizon Projection.
 * 2. Explicit Anomaly Legend: Clearly defines what red dots mean (Flagged Anomaly / Thermal Departure).
 * 3. Interactive Tooltip: Displays timestamp, telemetry value, model prediction, delta, and anomaly status.
 * 4. Rich Aesthetics: Neon cyan/amber gradients, subtle grid lines, drop shadows, and threshold indicators.
 */
export default function ChartPanel({
  title,
  subtitle,
  historicalData = [],
  forecastData = [],
  comparisonData = null, // Optional array of { timestamp, actual, predicted, is_anomaly }
  xKey = 'timestamp',
  yKey = 'value',
  unit = '',
  anomalies = [],
  warningThreshold = null,
  criticalThreshold = null,
  height = 260
}) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const [hoverSeries, setHoverSeries] = useState(null); // 'hist', 'forecast', 'comp'

  // Determine if this is a dual-series comparison on the same timeline
  const isComparisonMode = Boolean(comparisonData && comparisonData.length > 0);

  // Compute values range
  let allValues = [];
  if (isComparisonMode) {
    comparisonData.forEach((d) => {
      if (typeof d.actual === 'number') allValues.push(d.actual);
      if (typeof d.predicted === 'number') allValues.push(d.predicted);
      if (typeof d.value === 'number') allValues.push(d.value);
    });
  } else {
    historicalData.forEach((d) => {
      if (typeof d[yKey] === 'number') allValues.push(d[yKey]);
      if (typeof d.actual === 'number') allValues.push(d.actual);
      if (typeof d.predicted === 'number') allValues.push(d.predicted);
    });
    forecastData.forEach((d) => {
      if (typeof d[yKey] === 'number') allValues.push(d[yKey]);
      if (typeof d.predicted_temp === 'number') allValues.push(d.predicted_temp);
    });
  }

  allValues = allValues.filter((v) => typeof v === 'number' && !isNaN(v) && isFinite(v));

  if (allValues.length === 0) {
    return (
      <div
        className="glass-panel"
        style={{
          background: 'rgba(15, 23, 42, 0.85)',
          border: '1px solid rgba(56, 189, 248, 0.18)',
          borderRadius: '12px',
          padding: '24px',
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
        <span>Telemetry stream currently synchronizing with digital twin...</span>
      </div>
    );
  }

  let minVal = Math.min(...allValues);
  let maxVal = Math.max(...allValues);
  if (warningThreshold && isFinite(warningThreshold) && warningThreshold > maxVal && warningThreshold < maxVal * 1.5) {
    maxVal = warningThreshold;
  }
  const range = maxVal - minVal || 1;
  const paddingX = 45;
  const paddingTop = 25;
  const paddingBottom = 35;
  const chartHeight = height - 40;
  const width = 680;

  // Coordinate mapping
  const getY = (val) => {
    return chartHeight - paddingBottom - ((val - minVal) / range) * (chartHeight - paddingTop - paddingBottom);
  };

  // Count active anomalies in view
  let anomCount = 0;
  if (isComparisonMode) {
    anomCount = comparisonData.filter((d) => d.is_anomaly).length;
  } else {
    anomCount = historicalData.filter((d, i) => d.is_anomaly || anomalies.includes(i)).length;
  }

  // --------------------------------------------------------------------------
  // PATH GENERATION: Comparison Mode (Actual vs Predicted on SAME timeline)
  // --------------------------------------------------------------------------
  let compActualPath = '';
  let compActualArea = '';
  let compPredPath = '';
  let compStepX = 1;

  if (isComparisonMode && comparisonData.length > 0) {
    compStepX = (width - paddingX * 2) / Math.max(comparisonData.length - 1, 1);
    
    // Actual curve
    comparisonData.forEach((d, i) => {
      const val = typeof d.actual === 'number' ? d.actual : d.value;
      if (typeof val === 'number' && isFinite(val)) {
        const x = paddingX + i * compStepX;
        const y = getY(val);
        compActualPath += `${compActualPath === '' ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)} `;
      }
    });

    if (compActualPath) {
      const firstX = paddingX;
      const lastX = paddingX + (comparisonData.length - 1) * compStepX;
      const bottomY = chartHeight - paddingBottom;
      compActualArea = `${compActualPath} L ${lastX.toFixed(1)} ${bottomY} L ${firstX.toFixed(1)} ${bottomY} Z`;
    }

    // Predicted curve
    comparisonData.forEach((d, i) => {
      const val = typeof d.predicted === 'number' ? d.predicted : d.predicted_temp;
      if (typeof val === 'number' && isFinite(val)) {
        const x = paddingX + i * compStepX;
        const y = getY(val);
        compPredPath += `${compPredPath === '' ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)} `;
      }
    });
  }

  // --------------------------------------------------------------------------
  // PATH GENERATION: Sequential Mode (Historical Telemetry + Forward Horizon)
  // --------------------------------------------------------------------------
  let histPath = '';
  let histArea = '';
  let forecastPath = '';
  let forecastArea = '';
  let totalPoints = historicalData.length + forecastData.length;
  let stepX = (width - paddingX * 2) / Math.max(totalPoints - 1, 1);
  let boundaryX = paddingX + Math.max(0, historicalData.length - 1) * stepX;

  if (!isComparisonMode) {
    // Historical path
    historicalData.forEach((d, i) => {
      const val = d[yKey];
      if (typeof val === 'number' && isFinite(val)) {
        const x = paddingX + i * stepX;
        const y = getY(val);
        histPath += `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)} `;
      }
    });

    if (histPath && historicalData.length > 1) {
      const firstX = paddingX;
      const lastX = paddingX + (historicalData.length - 1) * stepX;
      const bottomY = chartHeight - paddingBottom;
      histArea = `${histPath} L ${lastX.toFixed(1)} ${bottomY} L ${firstX.toFixed(1)} ${bottomY} Z`;
    }

    // Forecast path (continuous from last historical point if available)
    if (historicalData.length > 0 && forecastData.length > 0) {
      const lastVal = historicalData[historicalData.length - 1][yKey];
      if (typeof lastVal === 'number' && isFinite(lastVal)) {
        const startX = paddingX + (historicalData.length - 1) * stepX;
        const startY = getY(lastVal);
        forecastPath = `M ${startX.toFixed(1)} ${startY.toFixed(1)} `;
      }
    }

    forecastData.forEach((d, i) => {
      const val = typeof d[yKey] === 'number' ? d[yKey] : d.predicted_temp;
      if (typeof val === 'number' && isFinite(val)) {
        const x = paddingX + (historicalData.length + i) * stepX;
        const y = getY(val);
        forecastPath += `${forecastPath === '' ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)} `;
      }
    });
  }

  // Active hover point resolution
  let activeTooltipData = null;
  if (hoverIndex !== null) {
    if (isComparisonMode && comparisonData[hoverIndex]) {
      const d = comparisonData[hoverIndex];
      const x = paddingX + hoverIndex * compStepX;
      const actVal = typeof d.actual === 'number' ? d.actual : d.value;
      const predVal = typeof d.predicted === 'number' ? d.predicted : d.predicted_temp;
      const y = actVal !== undefined ? getY(actVal) : getY(predVal);
      activeTooltipData = {
        x,
        y,
        time: d[xKey] || `Step ${hoverIndex}`,
        actual: actVal,
        predicted: predVal,
        delta: actVal !== undefined && predVal !== undefined ? (predVal - actVal).toFixed(2) : null,
        isAnomaly: Boolean(d.is_anomaly)
      };
    } else if (hoverSeries === 'hist' && historicalData[hoverIndex]) {
      const d = historicalData[hoverIndex];
      const x = paddingX + hoverIndex * stepX;
      const y = getY(d[yKey]);
      activeTooltipData = {
        x,
        y,
        time: d[xKey] || `Step ${hoverIndex}`,
        actual: d[yKey],
        predicted: d.predicted,
        isAnomaly: Boolean(d.is_anomaly || anomalies.includes(hoverIndex))
      };
    } else if (hoverSeries === 'forecast' && forecastData[hoverIndex]) {
      const d = forecastData[hoverIndex];
      const val = typeof d[yKey] === 'number' ? d[yKey] : d.predicted_temp;
      const x = paddingX + (historicalData.length + hoverIndex) * stepX;
      const y = getY(val);
      activeTooltipData = {
        x,
        y,
        time: d[xKey] || `+${(hoverIndex + 1) * 5}m`,
        predicted: val,
        isAnomaly: false
      };
    }
  }

  // Time ticks along the X-axis
  const timeLabels = [];
  if (isComparisonMode && comparisonData.length > 0) {
    const indices = [0, Math.floor(comparisonData.length / 2), comparisonData.length - 1];
    indices.forEach((idx) => {
      const item = comparisonData[idx];
      if (item) {
        timeLabels.push({
          x: paddingX + idx * compStepX,
          label: String(item[xKey] || '').replace(/^\d{4}-\d{2}-\d{2}[T\s]/, '').substring(0, 8)
        });
      }
    });
  } else if (historicalData.length > 0) {
    timeLabels.push({
      x: paddingX,
      label: String(historicalData[0][xKey] || '').replace(/^\d{4}-\d{2}-\d{2}[T\s]/, '').substring(0, 8)
    });
    if (historicalData.length > 4) {
      const mid = Math.floor(historicalData.length / 2);
      timeLabels.push({
        x: paddingX + mid * stepX,
        label: String(historicalData[mid][xKey] || '').replace(/^\d{4}-\d{2}-\d{2}[T\s]/, '').substring(0, 8)
      });
    }
    if (forecastData.length > 0) {
      timeLabels.push({
        x: boundaryX,
        label: 'Now'
      });
      timeLabels.push({
        x: width - paddingX,
        label: `+${forecastData.length * 5}m`
      });
    } else {
      timeLabels.push({
        x: width - paddingX,
        label: String(historicalData[historicalData.length - 1][xKey] || '').replace(/^\d{4}-\d{2}-\d{2}[T\s]/, '').substring(0, 8)
      });
    }
  }

  return (
    <div
      className="glass-panel"
      style={{
        background: 'linear-gradient(180deg, rgba(15, 23, 42, 0.92) 0%, rgba(10, 15, 30, 0.95) 100%)',
        border: '1px solid rgba(56, 189, 248, 0.22)',
        borderRadius: '12px',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 8px 32px -4px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.08)',
        position: 'relative'
      }}
    >
      {/* Chart Header & Action / Status Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '14px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13.5px', fontWeight: 700, color: '#f1f5f9', letterSpacing: '0.02em' }}>
              {title}
            </span>
            {anomCount > 0 ? (
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '10px',
                  background: 'rgba(239, 68, 68, 0.18)',
                  border: '1px solid #ef4444',
                  color: '#fca5a5'
                }}
              >
                ⚠️ {anomCount} Anomaly Event{anomCount > 1 ? 's' : ''} Flagged
              </span>
            ) : (
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '10px',
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  color: '#6ee7b7'
                }}
              >
                ✓ Nominal Telemetry
              </span>
            )}
          </div>
          {subtitle && (
            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
              {subtitle}
            </div>
          )}
        </div>

        {/* State-of-the-Art Interactive Legend */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '14px',
            fontSize: '11px',
            background: 'rgba(30, 41, 59, 0.6)',
            padding: '4px 10px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.06)'
          }}
        >
          {/* Cyan Telemetry Legend */}
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8', fontWeight: 600 }}>
            <span style={{ width: '14px', height: '3px', backgroundColor: '#38bdf8', borderRadius: '2px', display: 'inline-block' }} />
            Observed Telemetry
          </span>

          {/* Amber Forecast Legend */}
          {(isComparisonMode || forecastData.length > 0) && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#fbbf24', fontWeight: 600 }}>
              <span style={{ width: '14px', height: '2px', borderTop: '3px dashed #f59e0b', display: 'inline-block' }} />
              ML Forecast
            </span>
          )}

          {/* Red Anomaly Legend (explicitly states meaning) */}
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f87171', fontWeight: 600 }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: '#ef4444',
                border: '1.5px solid #ffffff',
                display: 'inline-block'
              }}
            />
            Red Dot: Flagged Anomaly Event
          </span>
        </div>
      </div>

      {/* SVG Canvas */}
      <svg
        viewBox={`0 0 ${width} ${chartHeight}`}
        style={{ width: '100%', height: `${chartHeight}px`, overflow: 'visible' }}
        onMouseLeave={() => {
          setHoverIndex(null);
          setHoverSeries(null);
        }}
      >
        <defs>
          {/* Cyan area gradient */}
          <linearGradient id="cyanGradientArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.0" />
          </linearGradient>

          {/* Amber area gradient */}
          <linearGradient id="amberGradientArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.0" />
          </linearGradient>

          {/* Glow filter */}
          <filter id="neonGlowCyan" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Horizontal grid lines & Y-axis scale */}
        {[0, 0.25, 0.5, 0.75, 1.0].map((pct, idx) => {
          const yPos = chartHeight - paddingBottom - pct * (chartHeight - paddingTop - paddingBottom);
          const gridVal = (minVal + pct * range).toFixed(1);
          return (
            <g key={idx}>
              <line
                x1={paddingX}
                y1={yPos}
                x2={width - paddingX}
                y2={yPos}
                stroke={idx === 0 ? 'rgba(71, 85, 105, 0.5)' : 'rgba(51, 65, 85, 0.35)'}
                strokeDasharray={idx === 0 ? 'none' : '3 4'}
              />
              <text
                x={paddingX - 8}
                y={yPos + 3.5}
                fill="#64748b"
                fontSize="10"
                textAnchor="end"
                fontFamily="monospace"
              >
                {gridVal}
                {unit}
              </text>
            </g>
          );
        })}

        {/* Warning Threshold Line (if provided) */}
        {warningThreshold && warningThreshold >= minVal && warningThreshold <= maxVal && (
          <g>
            <line
              x1={paddingX}
              y1={getY(warningThreshold)}
              x2={width - paddingX}
              y2={getY(warningThreshold)}
              stroke="#f59e0b"
              strokeWidth="1.2"
              strokeDasharray="4 4"
            />
            <text
              x={width - paddingX}
              y={getY(warningThreshold) - 5}
              fill="#fbbf24"
              fontSize="9"
              textAnchor="end"
              fontWeight="600"
            >
              Warning Threshold ({warningThreshold}{unit})
            </text>
          </g>
        )}

        {/* ==================== COMPARISON MODE DRAWING ==================== */}
        {isComparisonMode && (
          <>
            {/* Actual telemetry area fill */}
            {compActualArea && <path d={compActualArea} fill="url(#cyanGradientArea)" />}

            {/* Actual telemetry line */}
            {compActualPath && (
              <path
                d={compActualPath}
                fill="none"
                stroke="#38bdf8"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                filter="url(#neonGlowCyan)"
              />
            )}

            {/* Model prediction dashed line on same timeline */}
            {compPredPath && (
              <path
                d={compPredPath}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="2.2"
                strokeDasharray="5 4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}

            {/* Interactive hover targets & points */}
            {comparisonData.map((d, i) => {
              const x = paddingX + i * compStepX;
              const actVal = typeof d.actual === 'number' ? d.actual : d.value;
              const predVal = typeof d.predicted === 'number' ? d.predicted : d.predicted_temp;
              const yAct = actVal !== undefined ? getY(actVal) : null;
              const yPred = predVal !== undefined ? getY(predVal) : null;
              const isAnom = Boolean(d.is_anomaly);

              return (
                <g key={`comp-pt-${i}`}>
                  {/* Invisible broad hitbox for smooth hovering */}
                  <rect
                    x={x - compStepX / 2}
                    y={paddingTop}
                    width={compStepX}
                    height={chartHeight - paddingTop - paddingBottom}
                    fill="transparent"
                    onMouseEnter={() => {
                      setHoverIndex(i);
                      setHoverSeries('comp');
                    }}
                  />

                  {/* Anomaly marker ONLY if real anomaly flagged */}
                  {isAnom && yAct !== null && (
                    <circle
                      cx={x}
                      cy={yAct}
                      r="5"
                      fill="#ef4444"
                      stroke="#ffffff"
                      strokeWidth="1.8"
                      style={{ cursor: 'pointer', filter: 'drop-shadow(0 0 4px #ef4444)' }}
                    />
                  )}

                  {/* Hover highlight circle */}
                  {hoverIndex === i && yAct !== null && (
                    <circle cx={x} cy={yAct} r="4.5" fill="#38bdf8" stroke="#ffffff" strokeWidth="1.5" />
                  )}
                  {hoverIndex === i && yPred !== null && (
                    <circle cx={x} cy={yPred} r="4" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" />
                  )}
                </g>
              );
            })}
          </>
        )}

        {/* ==================== SEQUENTIAL MODE DRAWING ==================== */}
        {!isComparisonMode && (
          <>
            {/* Historical area fill */}
            {histArea && <path d={histArea} fill="url(#cyanGradientArea)" />}

            {/* Historical telemetry line */}
            {histPath && (
              <path
                d={histPath}
                fill="none"
                stroke="#38bdf8"
                strokeWidth="2.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                filter="url(#neonGlowCyan)"
              />
            )}

            {/* Horizon Divider Line (separates Now vs Future Forecast) */}
            {forecastData.length > 0 && (
              <g>
                <line
                  x1={boundaryX}
                  y1={paddingTop}
                  x2={boundaryX}
                  y2={chartHeight - paddingBottom}
                  stroke="rgba(245, 158, 11, 0.45)"
                  strokeDasharray="2 3"
                />
                <text
                  x={boundaryX}
                  y={paddingTop - 6}
                  fill="#fbbf24"
                  fontSize="9"
                  textAnchor="middle"
                  fontWeight="600"
                >
                  NOW / FUTURE HORIZON →
                </text>
              </g>
            )}

            {/* Forecast dashed line */}
            {forecastPath && (
              <path
                d={forecastPath}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="2.2"
                strokeDasharray="5 4"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            )}

            {/* Historical hover nodes and anomaly markers */}
            {historicalData.map((d, i) => {
              const x = paddingX + i * stepX;
              const val = d[yKey];
              if (typeof val !== 'number' || !isFinite(val)) return null;
              const y = getY(val);
              const isAnom = Boolean(d.is_anomaly || anomalies.includes(i));

              return (
                <g key={`hist-pt-${i}`}>
                  {/* Invisible hover hitbox */}
                  <rect
                    x={x - stepX / 2}
                    y={paddingTop}
                    width={stepX}
                    height={chartHeight - paddingTop - paddingBottom}
                    fill="transparent"
                    onMouseEnter={() => {
                      setHoverIndex(i);
                      setHoverSeries('hist');
                    }}
                  />

                  {/* Red dot rendered ONLY if confirmed anomaly */}
                  {isAnom && (
                    <circle
                      cx={x}
                      cy={y}
                      r="5"
                      fill="#ef4444"
                      stroke="#ffffff"
                      strokeWidth="1.8"
                      style={{ cursor: 'pointer', filter: 'drop-shadow(0 0 4px #ef4444)' }}
                    />
                  )}

                  {hoverIndex === i && hoverSeries === 'hist' && (
                    <circle cx={x} cy={y} r="4.5" fill="#38bdf8" stroke="#ffffff" strokeWidth="1.5" />
                  )}
                </g>
              );
            })}

            {/* Forecast hover nodes */}
            {forecastData.map((d, i) => {
              const x = paddingX + (historicalData.length + i) * stepX;
              const val = typeof d[yKey] === 'number' ? d[yKey] : d.predicted_temp;
              if (typeof val !== 'number' || !isFinite(val)) return null;
              const y = getY(val);

              return (
                <g key={`fc-pt-${i}`}>
                  <rect
                    x={x - stepX / 2}
                    y={paddingTop}
                    width={stepX}
                    height={chartHeight - paddingTop - paddingBottom}
                    fill="transparent"
                    onMouseEnter={() => {
                      setHoverIndex(i);
                      setHoverSeries('forecast');
                    }}
                  />
                  {hoverIndex === i && hoverSeries === 'forecast' && (
                    <circle cx={x} cy={y} r="4.5" fill="#f59e0b" stroke="#ffffff" strokeWidth="1.5" />
                  )}
                </g>
              );
            })}
          </>
        )}

        {/* X-axis baseline and timestamp markers */}
        <line
          x1={paddingX}
          y1={chartHeight - paddingBottom}
          x2={width - paddingX}
          y2={chartHeight - paddingBottom}
          stroke="rgba(71, 85, 105, 0.4)"
        />

        {timeLabels.map((tl, idx) => (
          <text
            key={`time-${idx}`}
            x={tl.x}
            y={chartHeight - paddingBottom + 16}
            fill="#64748b"
            fontSize="9.5"
            textAnchor="middle"
            fontFamily="monospace"
          >
            {tl.label}
          </text>
        ))}

        {/* Vertical crosshair tracker on hover */}
        {activeTooltipData && (
          <line
            x1={activeTooltipData.x}
            y1={paddingTop}
            x2={activeTooltipData.x}
            y2={chartHeight - paddingBottom}
            stroke="rgba(255, 255, 255, 0.35)"
            strokeDasharray="2 2"
          />
        )}
      </svg>

      {/* Interactive Floating Tooltip */}
      {activeTooltipData && (
        <div
          style={{
            position: 'absolute',
            left: `${Math.min(Math.max(activeTooltipData.x - 70, 15), width - 160)}px`,
            top: `${Math.max(15, activeTooltipData.y - 65)}px`,
            background: 'rgba(15, 23, 42, 0.95)',
            border: activeTooltipData.isAnomaly
              ? '1px solid #ef4444'
              : '1px solid rgba(56, 189, 248, 0.4)',
            borderRadius: '8px',
            padding: '8px 12px',
            fontSize: '11px',
            color: '#f8fafc',
            pointerEvents: 'none',
            boxShadow: '0 4px 16px rgba(0, 0, 0, 0.6)',
            zIndex: 10,
            minWidth: '130px'
          }}
        >
          <div style={{ color: '#94a3b8', fontSize: '10px', marginBottom: '4px', fontFamily: 'monospace' }}>
            ⏱ {activeTooltipData.time}
          </div>
          {activeTooltipData.actual !== undefined && (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
              <span style={{ color: '#38bdf8' }}>Observed:</span>
              <span style={{ fontWeight: 600 }}>{activeTooltipData.actual}{unit}</span>
            </div>
          )}
          {activeTooltipData.predicted !== undefined && (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
              <span style={{ color: '#fbbf24' }}>ML Forecast:</span>
              <span style={{ fontWeight: 600 }}>{activeTooltipData.predicted}{unit}</span>
            </div>
          )}
          {activeTooltipData.delta !== null && (
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px', fontSize: '10px', color: '#cbd5e1' }}>
              <span>Delta (Pred - Act):</span>
              <span>{activeTooltipData.delta > 0 ? `+${activeTooltipData.delta}` : activeTooltipData.delta}{unit}</span>
            </div>
          )}
          {activeTooltipData.isAnomaly ? (
            <div style={{ color: '#ef4444', fontWeight: 700, marginTop: '4px', fontSize: '10px' }}>
              🔴 SUPERVISED ANOMALY FLAGGED
            </div>
          ) : (
            <div style={{ color: '#10b981', fontSize: '10px', marginTop: '2px' }}>
              ✓ Nominal State
            </div>
          )}
        </div>
      )}
    </div>
  );
}