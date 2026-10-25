import React, { useMemo, useState, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

export default function Server3D({
  serverId = 'RACK-A01-SRV-04',
  rackId = 'RACK-A01',
  uPosition = 'U12 - U14',
  position = [0, 0.62, 0.04],
  isMonitored = false,
  telemetry = null,
  anomaly = null,
  viewMode = 'telemetry',
  isSelected = false,
  onSelectAsset,
  onHoverComponent
}) {
  const [hovered, setHovered] = useState(false);
  const ledRef = useRef();

  const hasAnomaly = Boolean(anomaly?.is_anomaly || (anomaly?.score && anomaly.score > 0.6));
  const tempVal = telemetry?.temp_core_max ?? 24.8;
  const powerVal = telemetry?.total_power ?? 1240.5;
  const fanRpm = telemetry?.fan_rpm ?? 4850;

  // CFD Continuous Thermal Color Map
  const thermalColor = useMemo(() => {
    if (!isMonitored) return new THREE.Color('#38bdf8');
    // Interpolate: 20°C (Cyan) -> 32°C (Emerald) -> 45°C (Amber) -> 75°C (Crimson)
    const norm = Math.min(Math.max((tempVal - 20) / 55, 0), 1);
    const color = new THREE.Color();
    if (norm < 0.25) {
      color.setRGB(0.0, 0.95, 1.0); // Cyan
    } else if (norm < 0.55) {
      color.setRGB(0.1, 0.9, 0.3); // Emerald/Green
    } else if (norm < 0.8) {
      color.setRGB(1.0, 0.65, 0.0); // Amber/Orange
    } else {
      color.setRGB(1.0, 0.05, 0.2); // Intense Crimson Red
    }
    return color;
  }, [isMonitored, tempVal]);

  const statusColor = useMemo(() => {
    if (hasAnomaly) return '#ff003b';
    if (!isMonitored) return '#38bdf8';
    if (tempVal > 40) return '#f59e0b';
    return '#10b981';
  }, [isMonitored, hasAnomaly, tempVal]);

  const chassisMaterial = useMemo(() => {
    if (viewMode === 'thermal' && isMonitored) {
      return new THREE.MeshStandardMaterial({
        color: thermalColor,
        roughness: 0.2,
        metalness: 0.6,
        emissive: thermalColor,
        emissiveIntensity: 0.45
      });
    }

    if (viewMode === 'anomaly' && hasAnomaly) {
      return new THREE.MeshStandardMaterial({
        color: '#dc2626',
        roughness: 0.2,
        metalness: 0.5,
        emissive: '#ff003b',
        emissiveIntensity: 0.6
      });
    }

    // Default: Sleek, high-contrast brushed metallic blade
    return new THREE.MeshStandardMaterial({
      color: isMonitored ? '#1e293b' : '#334155',
      roughness: 0.35,
      metalness: 0.75
    });
  }, [viewMode, isMonitored, thermalColor, hasAnomaly]);

  useFrame(({ clock }) => {
    if (hasAnomaly && ledRef.current) {
      const pulse = Math.sin(clock.getElapsedTime() * 9) * 0.5 + 0.5;
      ledRef.current.intensity = pulse * 2.5;
    }
  });

  const handlePointerOver = (e) => {
    e.stopPropagation();
    setHovered(true);
    if (onHoverComponent) {
      onHoverComponent({
        type: 'Server Blade (2U IBM AC922)',
        id: isMonitored ? 'm100-node1' : serverId,
        rackId,
        uPosition,
        isMonitored,
        status: hasAnomaly ? 'ANOMALOUS' : isMonitored ? 'NORMAL' : 'BASELINE',
        telemetry: isMonitored
          ? {
              temp: `${tempVal}°C`,
              power: `${powerVal} W`,
              fanSpeed: `${fanRpm} RPM`,
              statusText: hasAnomaly ? 'Isolation Forest Outlier Alert' : 'Nominal Stream'
            }
          : { statusText: 'Baseline Node (Operational)' }
      });
    }
  };

  const handlePointerOut = (e) => {
    e.stopPropagation();
    setHovered(false);
    if (onHoverComponent) onHoverComponent(null);
  };

  const handleClick = (e) => {
    e.stopPropagation();
    if (onSelectAsset) {
      onSelectAsset({
        id: isMonitored ? 'm100-node1' : serverId,
        name: isMonitored ? 'Marconi-100 HPC Blade Node 1' : `${serverId} Compute Node`,
        type: 'Compute Server (2x POWER9 + 4x Volta V100)',
        rack: rackId,
        slot: uPosition,
        status: hasAnomaly ? 'ANOMALOUS' : 'NORMAL',
        temperatures: telemetry
          ? {
              cpu0: tempVal,
              cpu1: Number((tempVal + 0.4).toFixed(1)),
              gpu0: Number((tempVal + 4.7).toFixed(1)),
              gpu1: Number((tempVal + 4.1).toFixed(1)),
              inlet: telemetry?.inlet_temp ?? 21.4
            }
          : null,
        powerWatts: telemetry?.total_power ?? telemetry?.power ?? powerVal,
        fansRpm: telemetry?.fan_rpm ?? fanRpm,
        timestamp: telemetry?.timestamp || 'Unavailable',
        mlAnomalyDetected: hasAnomaly,
        isolationForestScore: anomaly?.score || (isMonitored ? 0.042 : 'Unavailable'),
        pcaReconstructionError: anomaly?.pca_error || (isMonitored ? 0.018 : 'Unavailable'),
        forecastedTemp: isMonitored ? Number((tempVal + 0.5).toFixed(1)) : 'Unavailable',
        maintenanceRisk: hasAnomaly ? 'High' : isMonitored ? 'Low' : 'Unavailable',
        rootCauseHypothesis: hasAnomaly ? 'Cooling Fan Degradation / Tachometer Lag' : null
      });
    }
  };

  return (
    <group
      position={position}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
      onClick={handleClick}
    >
      {/* 2U Server Chassis Main Body */}
      <mesh material={chassisMaterial} castShadow receiveShadow>
        <boxGeometry args={[0.68, 0.16, 0.9]} />
      </mesh>

      {/* Front Faceplate with Silver Accent Bars */}
      <mesh position={[0, 0, 0.455]}>
        <planeGeometry args={[0.66, 0.14]} />
        <meshStandardMaterial
          color="#64748b"
          roughness={0.4}
          metalness={0.6}
          wireframe
        />
      </mesh>

      {/* NVMe Drive Bays (Brushed Silver) */}
      <mesh position={[-0.22, 0.02, 0.458]}>
        <boxGeometry args={[0.16, 0.08, 0.01]} />
        <meshStandardMaterial color="#cbd5e1" metalness={0.9} roughness={0.2} />
      </mesh>

      {/* Status LED Beacon */}
      <mesh position={[0.26, 0.04, 0.458]}>
        <boxGeometry args={[0.02, 0.02, 0.005]} />
        <meshBasicMaterial color={statusColor} toneMapped={false} />
      </mesh>
      <pointLight
        ref={ledRef}
        position={[0.26, 0.04, 0.47]}
        color={statusColor}
        intensity={isMonitored ? 1.2 : 0.4}
        distance={1.2}
      />

      {/* Network / Activity LED (Electric Cyan) */}
      <mesh position={[0.22, 0.04, 0.458]}>
        <boxGeometry args={[0.015, 0.015, 0.005]} />
        <meshBasicMaterial color="#00f2fe" toneMapped={false} />
      </mesh>

      {/* Chrome Server Latches */}
      <mesh position={[-0.32, 0, 0.47]}>
        <boxGeometry args={[0.02, 0.12, 0.03]} />
        <meshStandardMaterial color="#f8fafc" metalness={0.95} roughness={0.1} />
      </mesh>
      <mesh position={[0.32, 0, 0.47]}>
        <boxGeometry args={[0.02, 0.12, 0.03]} />
        <meshStandardMaterial color="#f8fafc" metalness={0.95} roughness={0.1} />
      </mesh>

      {/* Glowing Selection Cage */}
      {(isSelected || hovered) && (
        <lineSegments>
          <edgesGeometry args={[new THREE.BoxGeometry(0.7, 0.18, 0.92)]} />
          <lineBasicMaterial
            color={isSelected ? '#00f2fe' : hasAnomaly ? '#ff003b' : '#38bdf8'}
            linewidth={2}
          />
        </lineSegments>
      )}
    </group>
  );
}