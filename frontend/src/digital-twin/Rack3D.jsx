import React, { useMemo, useState } from 'react';
import * as THREE from 'three';
import Server3D from './Server3D';

function RackFrame({ isSelected, isHovered, hasAnomaly, isMonitoredNode }) {
  const edgeColor = useMemo(() => {
    if (hasAnomaly) return '#ff003b';
    if (isSelected) return '#00f2fe';
    if (isHovered) return '#38bdf8';
    if (isMonitoredNode) return '#00d8f6';
    return '#475569';
  }, [hasAnomaly, isSelected, isHovered, isMonitoredNode]);

  return (
    <group>
      {/* Outer 42U Cabinet Shell - Silver Titanium Finish */}
      <mesh position={[0, 1.1, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.82, 2.2, 1.12]} />
        <meshStandardMaterial
          color={isMonitoredNode ? '#334155' : '#1e293b'}
          roughness={0.35}
          metalness={0.65}
        />
      </mesh>

      {/* Internal Cabinet Cavity */}
      <mesh position={[0, 1.1, 0.05]}>
        <boxGeometry args={[0.74, 2.12, 0.98]} />
        <meshStandardMaterial color="#0f172a" roughness={0.7} />
      </mesh>

      {/* High-Luminance Perimeter Cage Outline */}
      <lineSegments position={[0, 1.1, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(0.84, 2.22, 1.14)]} />
        <lineBasicMaterial
          color={edgeColor}
          linewidth={isSelected || isMonitoredNode ? 2.5 : 1}
        />
      </lineSegments>

      {/* Perforated Mesh Front Door with Gloss Coating */}
      <mesh position={[0, 1.1, 0.57]}>
        <planeGeometry args={[0.78, 2.14]} />
        <meshStandardMaterial
          color={isMonitoredNode ? '#0284c7' : '#64748b'}
          roughness={0.3}
          metalness={0.7}
          transparent
          opacity={0.4}
          wireframe
        />
      </mesh>

      {/* Polished Roof Cap with Top Exhaust Vent */}
      <mesh position={[0, 2.21, 0]}>
        <boxGeometry args={[0.84, 0.04, 1.14]} />
        <meshStandardMaterial color="#475569" metalness={0.7} roughness={0.3} />
      </mesh>
    </group>
  );
}

function RackStatusBeacon({ hasAnomaly, isMonitoredNode, tempValue }) {
  const beaconColor = useMemo(() => {
    if (hasAnomaly) return '#ff003b';
    if (!isMonitoredNode) return '#0ea5e9'; // Cool ambient blue for baseline
    if (tempValue > 40) return '#f59e0b';   // Amber elevated
    return '#00f2fe';                       // High-visibility cyan
  }, [hasAnomaly, isMonitoredNode, tempValue]);

  return (
    <group position={[0, 2.23, 0.52]}>
      {/* Glowing Horizontal Light Strip */}
      <mesh>
        <boxGeometry args={[0.72, 0.04, 0.04]} />
        <meshBasicMaterial color={beaconColor} toneMapped={false} />
      </mesh>
      <pointLight color={beaconColor} intensity={hasAnomaly ? 2.0 : 0.8} distance={2.5} />
    </group>
  );
}

export default function Rack3D({
  id = 'RACK-A01',
  row = 'A',
  rackNum = 1,
  position = [0, 0, 0],
  rotation = [0, 0, 0],
  isMonitoredNode = false,
  telemetryData = null,
  mlAnomalyResult = null,
  viewMode = 'telemetry',
  selectedAsset = null,
  onSelectAsset,
  onHoverComponent
}) {
  const [isHovered, setIsHovered] = useState(false);

  const isSelected = selectedAsset?.rackId === id;
  const hasAnomaly = Boolean(mlAnomalyResult?.is_anomaly || mlAnomalyResult?.score > 0.6);
  const tempValue = telemetryData?.temp_core_max || 24.8;

  const serverSlots = useMemo(() => {
    return [
      { unitIndex: 1, uPosition: 'U36-U37', yPos: 1.82, serverId: `${id}-SRV-01` },
      { unitIndex: 2, uPosition: 'U28-U29', yPos: 1.42, serverId: `${id}-SRV-02` },
      { unitIndex: 3, uPosition: 'U20-U21', yPos: 1.02, serverId: `${id}-SRV-03` },
      { unitIndex: 4, uPosition: 'U12-U13', yPos: 0.62, serverId: `${id}-SRV-04` } // m100_node1 slot
    ];
  }, [id]);

  const handlePointerOver = (e) => {
    e.stopPropagation();
    setIsHovered(true);
    if (onHoverComponent) {
      onHoverComponent({
        type: 'Rack Cabinet (42U)',
        id,
        row,
        rackNum,
        isMonitoredNode,
        status: hasAnomaly ? 'ANOMALOUS' : isMonitoredNode ? 'NORMAL' : 'BASELINE',
        telemetry: isMonitoredNode
          ? {
              temp: `${tempValue}°C`,
              power: `${telemetryData?.total_power || 1240.5} W`,
              fanRpm: `${telemetryData?.fan_rpm || 4850} RPM`
            }
          : { statusText: 'Baseline Node (Operational)' }
      });
    }
  };

  const handlePointerOut = (e) => {
    e.stopPropagation();
    setIsHovered(false);
    if (onHoverComponent) onHoverComponent(null);
  };

  const handleClick = (e) => {
    e.stopPropagation();
    if (onSelectAsset) {
      onSelectAsset({
        rackId: id,
        id: isMonitoredNode ? 'm100-node1' : `${id}-NODE`,
        name: isMonitoredNode ? 'Marconi-100 HPC Blade Node 1' : `${id} Compute Node`,
        type: 'Compute Server (2x POWER9 + 4x Volta V100)',
        rack: id,
        slot: 'U12 - U14',
        status: hasAnomaly ? 'ANOMALOUS' : 'NORMAL',
        temperatures: telemetryData
          ? {
              cpu0: tempValue,
              cpu1: Number((tempValue + 0.4).toFixed(1)),
              gpu0: Number((tempValue + 4.7).toFixed(1)),
              gpu1: Number((tempValue + 4.1).toFixed(1)),
              inlet: telemetryData?.inlet_temp ?? 21.4
            }
          : null,
        powerWatts: telemetryData?.total_power ?? telemetryData?.power ?? 'Unavailable',
        fansRpm: telemetryData?.fan_rpm ?? 'Unavailable',
        timestamp: telemetryData?.timestamp || 'Unavailable',
        mlAnomalyDetected: hasAnomaly,
        isolationForestScore: mlAnomalyResult?.score || 0.042,
        pcaReconstructionError: mlAnomalyResult?.pca_error || 0.018,
        forecastedTemp: Number((tempValue + 0.5).toFixed(1)),
        maintenanceRisk: hasAnomaly ? 'High' : 'Low',
        rootCauseHypothesis: hasAnomaly ? 'Cooling airflow restriction / Fan tachometer lag' : null
      });
    }
  };

  return (
    <group
      position={position}
      rotation={rotation}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      <RackFrame
        isSelected={isSelected}
        isHovered={isHovered}
        hasAnomaly={hasAnomaly}
        isMonitoredNode={isMonitoredNode}
      />

      <RackStatusBeacon
        hasAnomaly={hasAnomaly}
        isMonitoredNode={isMonitoredNode}
        tempValue={tempValue}
      />

      {/* Populated Server Blades */}
      {serverSlots.map((slot) => {
        const isTargetBlade = isMonitoredNode && slot.unitIndex === 4;

        return (
          <Server3D
            key={slot.serverId}
            serverId={slot.serverId}
            rackId={id}
            uPosition={slot.uPosition}
            position={[0, slot.yPos, 0.04]}
            isMonitored={isTargetBlade}
            telemetry={isTargetBlade ? telemetryData : null}
            anomaly={isTargetBlade ? mlAnomalyResult : null}
            viewMode={viewMode}
            isSelected={selectedAsset?.id === (isTargetBlade ? 'm100-node1' : slot.serverId)}
            onSelectAsset={onSelectAsset}
            onHoverComponent={onHoverComponent}
          />
        );
      })}

      {/* Vented Airflow Blanking Panels with Clean Accent Tint */}
      {[0.22, 0.82, 1.22, 1.62, 2.02].map((y, idx) => (
        <mesh key={`blanking-${idx}`} position={[0, y, 0.48]}>
          <boxGeometry args={[0.68, 0.16, 0.02]} />
          <meshStandardMaterial color="#475569" roughness={0.4} metalness={0.6} />
        </mesh>
      ))}

      {/* Luminescent Rack Badge Plate */}
      <mesh position={[0, 2.14, 0.57]}>
        <planeGeometry args={[0.32, 0.06]} />
        <meshBasicMaterial color={isMonitoredNode ? '#00f2fe' : '#38bdf8'} />
      </mesh>
    </group>
  );
}