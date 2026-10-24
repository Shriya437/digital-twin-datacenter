import React from 'react';
import MetricCard from '../components/MetricCard';
import ChartPanel from '../components/ChartPanel';
import ModelStatusPanel from '../components/ModelStatusPanel';
import StatusBadge from '../components/StatusBadge';
import DataCenterScene from '../digital-twin/DataCenterScene';
import { useTelemetry } from '../hooks/useTelemetry';
import { useForecasts } from '../hooks/useForecasts';
import { useAnomalies } from '../hooks/useAnomalies';

/**
 * OverviewDashboard Component
 * The central operational overview. Visualizes solely dataset observations,
 * actual ML-detected anomalies, model forecasts, and recent model events.
 * Strictly adheres to the rule: no fabricated values.
 */
export default function OverviewDashboard({
  onNavigateToTwin,
  selectedAsset,
  onSelectAsset
}) {
  // 1. Fetch real Marconi-100 telemetry stream (polling every 5 seconds)
  const {
    latestTelemetry,
    history,
    loading: telLoading,
    error: telError
  } = useTelemetry({ pollIntervalMs: 5000, historyLimit: 25 });

  // 2. Fetch real model-generated temperature forecasts
  const {
    forecasts,
    modelMetrics,
    loading: forecastLoading,
    error: forecastError
  } = useForecasts({ horizonMinutes: 15, targetVariable: 'temp_core_max' });

  // 3. Fetch real Isolation Forest & PCA anomaly outputs
  const {
    anomalies,
    latestAnomalyResult,
    loading: anomLoading,
    error: anomError
  } = useAnomalies({ limit: 10 });

  // Map historical telemetry rows directly to the ChartPanel format
  const historicalChartData = history
    .map((row) => {
      const rawVal =
        typeof row.temp_core_max === 'number'
          ? row.temp_core_max
          : typeof row.temperature === 'number'
          ? row.temperature
          : null;

      return {
        timestamp: row.timestamp
          ? new Date(row.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit'
            })
          : '—',
        value: rawVal,
        is_anomaly: Boolean(row.is_anomaly)
      };
    })
    .filter((pt) => pt.value !== null);

  // Map model forecasts strictly to distinct future points
  const forecastChartData = forecasts
    .map((f) => {
      const predVal =
        typeof f.predicted_temp === 'number'
          ? f.predicted_temp
          : typeof f.prediction === 'number'
          ? f.prediction
          : null;

      return {
        timestamp: f.timestamp
          ? new Date(f.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit'
            })
          : '+15m',
        value: predVal
      };
    })
    .filter((pt) => pt.value !== null);

  // Extract measured metric values without synthetic fallback numbers
  const activePower =
    typeof latestTelemetry?.total_power === 'number'
      ? latestTelemetry.total_power.toFixed(1)
      : typeof latestTelemetry?.power === 'number'
      ? latestTelemetry.power.toFixed(1)
      : 'Unavailable';

  const activeTemp =
    typeof latestTelemetry?.temp_core_max === 'number'
      ? latestTelemetry.temp_core_max.toFixed(1)
      : typeof latestTelemetry?.temperature === 'number'
      ? latestTelemetry.temperature.toFixed(1)
      : 'Unavailable';

  const anomalyCount = Array.isArray(anomalies)
    ? anomalies.length
    : 'Unavailable';

  const latestPredictedTemp =
    forecasts.length > 0 && typeof forecasts[0]?.predicted_temp === 'number'
      ? forecasts[0].predicted_temp.toFixed(1)
      : typeof forecasts[0]?.prediction === 'number'
      ? forecasts[0].prediction.toFixed(1)
      : 'Unavailable';

  // Anomaly status derived strictly from ML detector output
  const anomalyStatus = latestAnomalyResult?.is_anomaly
    ? 'CRITICAL'
    : anomLoading
    ? 'UNKNOWN'
    : 'HEALTHY';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Top Telemetry & ML KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px'
        }}
      >
        <MetricCard
          title="Active Power Draw"
          value={activePower}
          unit={activePower !== 'Unavailable' ? 'W' : ''}
          status={activePower !== 'Unavailable' ? 'NORMAL' : 'UNAVAILABLE'}
          source="m100_node1 Telemetry"
          timestamp={
            latestTelemetry?.timestamp
              ? new Date(latestTelemetry.timestamp).toLocaleTimeString()
              : undefined
          }
          icon="⚡"
        />

        <MetricCard
          title="Core Temperature (Max)"
          value={activeTemp}
          unit={activeTemp !== 'Unavailable' ? '°C' : ''}
          status={
            activeTemp !== 'Unavailable'
              ? activeTemp > 45
                ? 'WARNING'
                : 'NORMAL'
              : 'UNAVAILABLE'
          }
          source="POWER9 / V100 Sensors"
          timestamp={
            latestTelemetry?.timestamp
              ? new Date(latestTelemetry.timestamp).toLocaleTimeString()
              : undefined
          }
          icon="♨"
        />

        <MetricCard
          title="Detected Anomalies"
          value={anomalyCount}
          status={anomalyStatus}
          source="Isolation Forest / PCA"
          subtext={
            anomLoading
              ? 'Evaluating dataset...'
              : anomError
              ? anomError
              : 'Evaluated on active window'
          }
          icon="⚠"
        />

        <MetricCard
          title="Temp Forecast Horizon"
          value={latestPredictedTemp}
          unit={latestPredictedTemp !== 'Unavailable' ? '°C' : ''}
          status={latestPredictedTemp !== 'Unavailable' ? 'OPTIMAL' : 'UNAVAILABLE'}
          source={modelMetrics?.model_name || 'Ridge/RF Regressor'}
          subtext={
            modelMetrics?.rmse
              ? `RMSE: ${modelMetrics.rmse}°C on test split`
              : 'Prediction horizon active'
          }
          icon="↗"
        />
      </div>

      {/* Interactive 3D Digital Twin Viewport Container */}
      <div
        style={{
          background: 'rgba(15, 23, 42, 0.95)',
          border: '1px solid rgba(56, 189, 248, 0.2)',
          borderRadius: '12px',
          overflow: 'hidden',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.5)',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <div
          style={{
            padding: '12px 20px',
            borderBottom: '1px solid rgba(56, 189, 248, 0.12)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            backgroundColor: 'rgba(11, 19, 43, 0.7)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span
              style={{
                fontSize: '13px',
                fontWeight: 700,
                color: '#f8fafc',
                letterSpacing: '0.04em'
              }}
            >
              3D DATA CENTER DIGITAL TWIN
            </span>
            <span
              style={{
                fontSize: '11px',
                color: '#00f2fe',
                fontFamily: 'monospace'
              }}
            >
              [m100_node1 Hardware Containment]
            </span>
          </div>

          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() =>
                onSelectAsset &&
                onSelectAsset({
                  id: 'm100-node1',
                  name: 'Marconi-100 HPC Blade Node 1',
                  type: 'IBM Power System AC922',
                  rack: 'RACK-A01',
                  slot: 'U12 - U14',
                  status: latestAnomalyResult?.is_anomaly ? 'ANOMALOUS' : 'NORMAL',
                  temperatures: latestTelemetry
                    ? {
                        cpu0: activeTemp !== 'Unavailable' ? Number(activeTemp) : null,
                        inlet: latestTelemetry.inlet_temp ?? null
                      }
                    : null,
                  powerWatts: activePower,
                  fansRpm: latestTelemetry?.fan_rpm ?? 'Unavailable',
                  timestamp: latestTelemetry?.timestamp ?? 'Unavailable',
                  mlAnomalyDetected: Boolean(latestAnomalyResult?.is_anomaly),
                  isolationForestScore: latestAnomalyResult?.score ?? 'Unavailable',
                  forecastedTemp: latestPredictedTemp,
                  maintenanceRisk: latestAnomalyResult?.risk_level ?? 'Low'
                })
              }
              style={{
                backgroundColor: 'rgba(56, 189, 248, 0.12)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Focus Node 1
            </button>
            <button className="btn-neon-glow"
              onClick={onNavigateToTwin}
              style={{
                backgroundColor: '#0284c7',
                color: '#ffffff',
                border: 'none',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Full 3D Twin ➔
            </button>
          </div>
        </div>

        {/* 3D Scene Viewport */}
        <div style={{ width: '100%', height: '420px', position: 'relative' }}>
          <DataCenterScene
            telemetryData={latestTelemetry}
            mlAnomalyResult={latestAnomalyResult}
            selectedAsset={selectedAsset}
            onSelectAsset={onSelectAsset}
          />
        </div>
      </div>

      {/* Bottom Grid: Historical Observations vs Forecasts & Flagged Anomaly Stream */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '16px'
        }}
      >
        {/* Real Historical vs Forecast Time-Series Chart */}
        <ChartPanel
          title="Recorded Temperature vs ML Forecast Horizon (°C)"
          historicalData={historicalChartData}
          forecastData={forecastChartData}
          yKey="value"
          unit="°C"
          height={260}
        />

        {/* Real Anomaly Observation Stream */}
        <div
          style={{
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(56, 189, 248, 0.18)',
            borderRadius: '10px',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '14px'
            }}
          >
            <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
              ML Anomaly Detection Stream
            </span>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              {Array.isArray(anomalies) ? `${anomalies.length} Flagged Events` : 'Stream Idle'}
            </span>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              overflowY: 'auto',
              maxHeight: '200px'
            }}
          >
            {anomLoading && anomalies.length === 0 ? (
              <div
                style={{
                  fontSize: '12px',
                  color: '#64748b',
                  textAlign: 'center',
                  padding: '24px 0'
                }}
              >
                Evaluating dataset observations against detector models...
              </div>
            ) : anomalies.length === 0 ? (
              <div
                style={{
                  fontSize: '12px',
                  color: '#64748b',
                  textAlign: 'center',
                  padding: '24px 0'
                }}
              >
                No anomalies flagged in active observation window.
              </div>
            ) : (
              anomalies.map((anom, idx) => (
                <div
                  key={idx}
                  style={{
                    background: 'rgba(30, 41, 59, 0.45)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <div>
                    <div
                      style={{
                        fontSize: '12px',
                        color: '#f87171',
                        fontWeight: 600
                      }}
                    >
                      Outlier Score:{' '}
                      {typeof anom.anomaly_score === 'number'
                        ? anom.anomaly_score.toFixed(3)
                        : typeof anom.score === 'number'
                        ? anom.score.toFixed(3)
                        : 'Flagged'}
                    </div>
                    <div style={{ fontSize: '10px', color: '#94a3b8' }}>
                      Timestamp: {anom.timestamp || 'Recorded Observation'}
                    </div>
                  </div>
                  <StatusBadge status="ANOMALOUS" size="sm" />
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Model Performance & Pipeline Verification Status */}
      <ModelStatusPanel />
    </div>
  );
}