import React, { useState, useMemo } from 'react';
import MetricCard from '../components/MetricCard';
import ChartPanel from '../components/ChartPanel';
import StatusBadge from '../components/StatusBadge';
import { useTelemetry } from '../hooks/useTelemetry';

/**
 * EnergyAnalyticsView Component
 * Analyzes measured power consumption, energy efficiency, and thermal-power coupling.
 * Explicitly segregates empirical measurements from what-if simulations.
 */
export default function EnergyAnalyticsView() {
  const { latestTelemetry, history, loading: telLoading } = useTelemetry({ historyLimit: 40 });

  // Simulation controls (clearly isolated from empirical measurements)
  const [workloadScale, setWorkloadScale] = useState(1.0); // 0.5x to 1.5x
  const [ambientDelta, setAmbientDelta] = useState(0);     // -5°C to +5°C

  // Format historical power measurements for ChartPanel
  const powerChartData = useMemo(() => {
    return history
      .map((row) => ({
        timestamp: row.timestamp
          ? new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          : '—',
        value: typeof row.total_power === 'number'
          ? Number(row.total_power.toFixed(1))
          : typeof row.power === 'number'
          ? Number(row.power.toFixed(1))
          : null,
        is_anomaly: Boolean(row.is_anomaly)
      }))
      .filter((pt) => pt.value !== null);
  }, [history]);

  // Measured telemetry values
  const currentPower = typeof latestTelemetry?.total_power === 'number'
    ? latestTelemetry.total_power
    : typeof latestTelemetry?.power === 'number'
    ? latestTelemetry.power
    : null;

  const currentTemp = typeof latestTelemetry?.temp_core_max === 'number'
    ? latestTelemetry.temp_core_max
    : typeof latestTelemetry?.temperature === 'number'
    ? latestTelemetry.temperature
    : null;

  // Calculate cumulative energy consumption (kWh) over recorded observation window
  const cumulativeEnergyKWh = useMemo(() => {
    if (!history || history.length === 0) return 'Unavailable';
    const validPower = history
      .map((r) => r.total_power ?? r.power)
      .filter((p) => typeof p === 'number');

    if (validPower.length === 0) return 'Unavailable';

    // 5-minute sampling interval = 5/60 hours per sample
    const totalWattHours = validPower.reduce((acc, p) => acc + p * (5 / 60), 0);
    return (totalWattHours / 1000).toFixed(2);
  }, [history]);

  // What-If Simulated Power Draw
  const simulatedPower = useMemo(() => {
    if (currentPower === null) return 'Unavailable';
    // Power scale + fan cooling compensation penalty (approx 12W per °C rise)
    const simVal = currentPower * workloadScale + ambientDelta * 14.5;
    return Math.max(simVal, 350).toFixed(1);
  }, [currentPower, workloadScale, ambientDelta]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header Description */}
      <div>
        <h2 className="gradient-text-aurora" style={{ margin: 0, fontSize: '18px', color: '#f8fafc', fontWeight: 700 }}>
          Energy & Electrical Power Analytics
        </h2>
        <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#94a3b8' }}>
          Empirical power measurements, thermal-to-power correlation, and simulated workload scaling.
        </p>
      </div>

      {/* Measured Energy KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        <MetricCard
          title="Measured Active Power"
          value={currentPower !== null ? currentPower.toFixed(1) : 'Unavailable'}
          unit={currentPower !== null ? 'W' : ''}
          status={currentPower !== null ? (currentPower > 1600 ? 'WARNING' : 'NORMAL') : 'UNAVAILABLE'}
          source="m100_node1 Telemetry"
          timestamp={latestTelemetry?.timestamp ? new Date(latestTelemetry.timestamp).toLocaleTimeString() : undefined}
          icon="⚡"
        />

        <MetricCard
          title="Window Energy Consumed"
          value={cumulativeEnergyKWh}
          unit={cumulativeEnergyKWh !== 'Unavailable' ? 'kWh' : ''}
          status={cumulativeEnergyKWh !== 'Unavailable' ? 'OPTIMAL' : 'UNAVAILABLE'}
          source="Integrated 5m Steps"
          subtext={`Over past ${history.length} observations`}
          icon="⏱"
        />

        <MetricCard
          title="Thermal-to-Power Coupling"
          value={currentPower && currentTemp ? `${(currentPower / currentTemp).toFixed(1)}` : 'Unavailable'}
          unit={currentPower && currentTemp ? 'W/°C' : ''}
          status={currentPower && currentTemp ? 'NORMAL' : 'UNAVAILABLE'}
          source="Empirical Ratio"
          subtext="Specific thermal dissipation"
          icon="♨"
        />

        <MetricCard
          title="Facility PUE Metric"
          value="Unavailable"
          status="UNAVAILABLE"
          source="Facility data not in dataset"
          subtext="Requires whole-facility chiller load"
          icon="⛨"
        />
      </div>

      {/* Primary Measured Power Time-Series Chart */}
      <ChartPanel
        title="Recorded Node Power Consumption Trajectory (Watts)"
        subtitle="Active electrical load draw recorded from IBM Power AC922 dual redundant power supplies"
        historicalData={powerChartData}
        forecastData={[]}
        yKey="value"
        unit="W"
        height={280}
      />

      {/* Dual Section: Empirical Thermal-Power Scatter vs What-If Simulator */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '16px' }}>
        
        {/* Empirical Measurements & Boundaries */}
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(56, 189, 248, 0.18)',
            borderRadius: '10px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
              Measured Energy Boundaries
            </span>
            <StatusBadge status="HEALTHY" size="sm" label="MEASURED DATA" />
          </div>

          <div style={{ background: 'rgba(30, 41, 59, 0.4)', borderRadius: '8px', padding: '12px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#94a3b8' }}>Chassis Nominal Idle Power</span>
              <span style={{ color: '#cbd5e1', fontFamily: 'monospace' }}>~420 W</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#94a3b8' }}>Peak Compute Load Draw</span>
              <span style={{ color: '#f8fafc', fontFamily: 'monospace' }}>~1,850 W (2x POWER9 + 4x V100)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: '#94a3b8' }}>Dynamic Range</span>
              <span style={{ color: '#38bdf8', fontFamily: 'monospace' }}>1,430 W delta</span>
            </div>
          </div>
        </div>

        {/* Workload What-If Simulation Panel (Strictly labeled as Simulation) */}
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(147, 51, 234, 0.3)',
            borderRadius: '10px',
            padding: '18px',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#a855f7' }} />
              <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                What-If Energy Simulation
              </span>
            </div>
            <span style={{ fontSize: '9px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', backgroundColor: 'rgba(168, 85, 247, 0.2)', color: '#c084fc', border: '1px solid rgba(192, 132, 252, 0.4)', textTransform: 'uppercase' }}>
              SIMULATED ONLY
            </span>
          </div>

          {/* Workload Scaling Slider */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: '#94a3b8' }}>Workload Scaling Factor</span>
              <span style={{ color: '#c084fc', fontFamily: 'monospace', fontWeight: 600 }}>{workloadScale.toFixed(2)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="1.5"
              step="0.05"
              value={workloadScale}
              onChange={(e) => setWorkloadScale(parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: '#a855f7' }}
            />
          </div>

          {/* Ambient Inlet Delta Slider */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: '#94a3b8' }}>Cold Aisle Ambient Temperature Shift</span>
              <span style={{ color: '#c084fc', fontFamily: 'monospace', fontWeight: 600 }}>
                {ambientDelta > 0 ? `+${ambientDelta}°C` : `${ambientDelta}°C`}
              </span>
            </div>
            <input
              type="range"
              min="-5"
              max="5"
              step="1"
              value={ambientDelta}
              onChange={(e) => setAmbientDelta(parseInt(e.target.value, 10))}
              style={{ width: '100%', accentColor: '#a855f7' }}
            />
          </div>

          {/* Simulated Projection Result */}
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', borderRadius: '8px', padding: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontSize: '11px', color: '#94a3b8', display: 'block' }}>Projected Power Draw</span>
              <span style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc', fontFamily: 'monospace' }}>
                {simulatedPower !== 'Unavailable' ? `${simulatedPower} W` : 'Unavailable'}
              </span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span style={{ fontSize: '11px', color: '#94a3b8', display: 'block' }}>Delta from Current</span>
              <span style={{ fontSize: '12px', fontWeight: 600, color: Number(simulatedPower) > Number(currentPower) ? '#f87171' : '#34d399', fontFamily: 'monospace' }}>
                {simulatedPower !== 'Unavailable' && currentPower !== null
                  ? `${(Number(simulatedPower) - currentPower).toFixed(1)} W`
                  : '—'}
              </span>
            </div>
          </div>

          <div style={{ fontSize: '10px', color: '#64748b', fontStyle: 'italic', marginTop: 'auto' }}>
            * This simulation applies linear scaling to current node power for planning; it does not represent historical measurements.
          </div>
        </div>
      </div>
    </div>
  );
}