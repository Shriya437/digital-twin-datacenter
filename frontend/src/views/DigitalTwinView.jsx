import React, { useState } from 'react';
import DataCenterScene from '../digital-twin/DataCenterScene';
import AssetDetailPanel from '../components/AssetDetailPanel';
import StatusBadge from '../components/StatusBadge';
import { useTelemetry } from '../hooks/useTelemetry';
import { useAnomalies } from '../hooks/useAnomalies';
import { useForecasts } from '../hooks/useForecasts';

/**
 * DigitalTwinView Component
 * Dedicated full-viewport 3D operational environment.
 * Maps real Marconi-100 node telemetry and ML detector outputs to 3D equipment.
 */
export default function DigitalTwinView({
  selectedAsset,
  onSelectAsset
}) {
  // 1. Fetch real telemetry stream for m100_node1
  const {
    latestTelemetry,
    loading: telLoading,
    error: telError
  } = useTelemetry({ pollIntervalMs: 3000 });

  // 2. Fetch real Isolation Forest & PCA anomaly outputs
  const {
    latestAnomalyResult,
    anomalies,
    loading: anomLoading
  } = useAnomalies({ limit: 5 });

  // 3. Fetch model forecasts
  const {
    forecasts,
    modelMetrics
  } = useForecasts({ horizonMinutes: 15, targetVariable: 'temp_core_max' });

  const [panelOpen, setPanelOpen] = useState(true);

  // Extract real measured values without synthetic placeholders
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

  const latestPredictedTemp =
    forecasts.length > 0 && typeof forecasts[0]?.predicted_temp === 'number'
      ? forecasts[0].predicted_temp.toFixed(1)
      : 'Unavailable';

  const isAnomaly = Boolean(latestAnomalyResult?.is_anomaly);

  // Quick action to focus on primary telemetry node m100_node1
  const handleFocusNode1 = () => {
    if (onSelectAsset) {
      onSelectAsset({
        rackId: 'RACK-A01',
        id: 'm100-node1',
        name: 'Marconi-100 HPC Blade Node 1',
        type: 'IBM Power System AC922 (2x POWER9 + 4x Volta V100)',
        rack: 'RACK-A01',
        slot: 'U12 - U14',
        status: isAnomaly ? 'ANOMALOUS' : 'NORMAL',
        temperatures: latestTelemetry
          ? {
              cpu0: activeTemp !== 'Unavailable' ? Number(activeTemp) : null,
              inlet: latestTelemetry.inlet_temp ?? null
            }
          : null,
        powerWatts: activePower,
        fansRpm: latestTelemetry?.fan_rpm ?? 'Unavailable',
        timestamp: latestTelemetry?.timestamp ?? 'Unavailable',
        mlAnomalyDetected: isAnomaly,
        isolationForestScore: latestAnomalyResult?.score ?? 'Unavailable',
        pcaReconstructionError: latestAnomalyResult?.pca_residual ?? 'Unavailable',
        forecastedTemp: latestPredictedTemp,
        maintenanceRisk: latestAnomalyResult?.risk_level ?? 'Low',
        rootCauseHypothesis: isAnomaly ? 'Cooling airflow restriction / Fan tachometer lag' : null
      });
      setPanelOpen(true);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 110px)',
        position: 'relative',
        overflow: 'hidden',
        borderRadius: '12px',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        backgroundColor: '#040814'
      }}
    >
      {/* Top Utility HUD Header */}
      <div
        style={{
          padding: '12px 20px',
          borderBottom: '1px solid rgba(56, 189, 248, 0.15)',
          backgroundColor: 'rgba(11, 19, 43, 0.95)',
          backdropFilter: 'blur(10px)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          zIndex: 30
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div>
            <span style={{ fontSize: '14px', fontWeight: 700, color: '#f8fafc', letterSpacing: '0.04em' }}>
              3D FACILITY DIGITAL TWIN
            </span>
            <span style={{ fontSize: '11px', color: '#38bdf8', marginLeft: '8px' }}>
              CINECA Marconi-100 Cluster Pod
            </span>
          </div>

          <StatusBadge
            status={isAnomaly ? 'CRITICAL' : telLoading ? 'UNAVAILABLE' : 'HEALTHY'}
            label={isAnomaly ? 'ANOMALY DETECTED' : telLoading ? 'STREAM CONNECTING' : 'TELEMETRY NOMINAL'}
            size="sm"
          />
        </div>

        {/* Telemetry Snapshot and Quick Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: '#94a3b8' }}>
            <div>
              Power: <strong style={{ color: '#f8fafc', fontFamily: 'monospace' }}>{activePower !== 'Unavailable' ? `${activePower} W` : 'Unavailable'}</strong>
            </div>
            <div>
              Max Temp: <strong style={{ color: '#38bdf8', fontFamily: 'monospace' }}>{activeTemp !== 'Unavailable' ? `${activeTemp} °C` : 'Unavailable'}</strong>
            </div>
            <div>
              Forecast: <strong style={{ color: '#34d399', fontFamily: 'monospace' }}>{latestPredictedTemp !== 'Unavailable' ? `${latestPredictedTemp} °C` : 'Unavailable'}</strong>
            </div>
          </div>

          <button
            onClick={handleFocusNode1}
            style={{
              backgroundColor: 'rgba(56, 189, 248, 0.15)',
              color: '#00f2fe',
              border: '1px solid rgba(56, 189, 248, 0.35)',
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            Target Node 1
          </button>

          <button
            onClick={() => setPanelOpen(!panelOpen)}
            style={{
              backgroundColor: panelOpen ? 'rgba(14, 165, 233, 0.25)' : 'rgba(30, 41, 59, 0.5)',
              color: panelOpen ? '#38bdf8' : '#94a3b8',
              border: '1px solid rgba(56, 189, 248, 0.2)',
              padding: '6px 12px',
              borderRadius: '6px',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            {panelOpen ? 'Hide Inspector ✕' : 'Show Inspector ➔'}
          </button>
        </div>
      </div>

      {/* Main 3D Viewport with Integrated Side Inspection Drawer */}
      <div style={{ display: 'flex', flex: 1, position: 'relative', overflow: 'hidden' }}>
        
        {/* Full Interactive 3D Scene Viewport */}
        <div style={{ flex: 1, position: 'relative', height: '100%' }}>
          <DataCenterScene
            telemetryData={latestTelemetry}
            mlAnomalyResult={latestAnomalyResult}
            selectedAsset={selectedAsset}
            onSelectAsset={(asset) => {
              if (onSelectAsset) onSelectAsset(asset);
              setPanelOpen(true);
            }}
          />
        </div>

        {/* Collapsible Asset Detail Panel */}
        {panelOpen && (
          <div
            style={{
              position: 'relative',
              height: '100%',
              zIndex: 35
            }}
          >
            <AssetDetailPanel
              selectedAsset={selectedAsset}
              onClose={() => setPanelOpen(false)}
            />
          </div>
        )}
      </div>

      {/* Connection & Provenance Footnote Bar */}
      <div
        style={{
          padding: '6px 18px',
          backgroundColor: 'rgba(11, 19, 43, 0.95)',
          borderTop: '1px solid rgba(56, 189, 248, 0.12)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '10px',
          color: '#64748b',
          zIndex: 30
        }}
      >
        <div>
          Mapping Rule: Telemetry actively drives <code>RACK-A01</code>. Adjacent racks represent unmonitored baseline hardware.
        </div>
        <div style={{ fontFamily: 'monospace', color: '#94a3b8' }}>
          Observation: {latestTelemetry?.timestamp || 'Dataset Stream Active'}
        </div>
      </div>
    </div>
  );
}