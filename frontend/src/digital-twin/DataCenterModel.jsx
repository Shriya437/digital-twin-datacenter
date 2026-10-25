import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import Rack3D from './Rack3D';
import SensorMarker3D from './SensorMarker3D';

/**
 * Architectural CRAH Unit (Chilled Water Air Handler)
 * Styled in hospital-grade cleanroom powder coat with real air louvers and state beacon.
 */
function CRAHUnit({ position, rotation = [0, 0, 0] }) {
  return (
    <group position={position} rotation={rotation}>
      {/* Heavy Powder-Coated Outer Frame */}
      <mesh position={[0, 2.5, 0]} castShadow receiveShadow>
        <boxGeometry args={[2.6, 5.0, 1.5]} />
        <meshStandardMaterial
          color="#f1f5f9"
          roughness={0.25}
          metalness={0.35}
        />
      </mesh>

      {/* Recessed Technical Louver Grille */}
      <mesh position={[0, 2.5, 0.76]}>
        <planeGeometry args={[2.2, 4.2]} />
        <meshStandardMaterial
          color="#0284c7"
          roughness={0.3}
          metalness={0.6}
          wireframe
        />
      </mesh>

      {/* Luminous Intake Flow Indicator */}
      <mesh position={[0, 4.8, 0.77]}>
        <boxGeometry args={[2.3, 0.12, 0.05]} />
        <meshBasicMaterial color="#00d2ff" toneMapped={false} />
      </mesh>

      {/* Access Door Handle & Digital Service Tag */}
      <mesh position={[1.0, 2.4, 0.77]}>
        <boxGeometry args={[0.08, 0.6, 0.04]} />
        <meshStandardMaterial color="#64748b" metalness={0.9} roughness={0.1} />
      </mesh>
    </group>
  );
}

/**
 * Overhead Cable Trays & High-Voltage Busways
 * Clean industrial aluminum cable ladders with color-coded power & fiber feeds.
 */
function CableTray({ position, length = 18 }) {
  return (
    <group position={position}>
      {/* Aluminum Structural Tray */}
      <mesh position={[0, 0, 0]} castShadow>
        <boxGeometry args={[length, 0.12, 0.9]} />
        <meshStandardMaterial
          color="#cbd5e1"
          metalness={0.7}
          roughness={0.3}
        />
      </mesh>

      {/* Primary Bus A (Vibrant Azure Fiber) */}
      <mesh position={[0, 0.1, -0.25]}>
        <boxGeometry args={[length, 0.06, 0.1]} />
        <meshBasicMaterial color="#0284c7" toneMapped={false} />
      </mesh>

      {/* Primary Bus B (Vibrant Emerald Secondary Line) */}
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={[length, 0.06, 0.1]} />
        <meshBasicMaterial color="#10b981" toneMapped={false} />
      </mesh>

      {/* Critical DC Bus (Amber High-Current Busway) */}
      <mesh position={[0, 0.1, 0.25]}>
        <boxGeometry args={[length, 0.06, 0.1]} />
        <meshBasicMaterial color="#f59e0b" toneMapped={false} />
      </mesh>
    </group>
  );
}

/**
 * Cleanroom Architectural Facility Enclosure
 * Clean white-and-steel aesthetic with true raised-floor tiling and thermal zoning.
 */
function StructuralEnclosure() {
  return (
    <group>
      {/* Main Perimeter Architectural Enclosure Walls */}
      <mesh position={[0, 4.5, -11]} receiveShadow>
        <boxGeometry args={[28, 9.0, 0.4]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.4} metalness={0.1} />
      </mesh>
      <mesh position={[0, 4.5, 11]} receiveShadow>
        <boxGeometry args={[28, 9.0, 0.4]} />
        <meshStandardMaterial color="#f8fafc" roughness={0.4} metalness={0.1} />
      </mesh>
      <mesh position={[-14, 4.5, 0]} receiveShadow>
        <boxGeometry args={[0.4, 9.0, 22]} />
        <meshStandardMaterial color="#f1f5f9" roughness={0.5} metalness={0.1} />
      </mesh>
      <mesh position={[14, 4.5, 0]} receiveShadow>
        <boxGeometry args={[0.4, 9.0, 22]} />
        <meshStandardMaterial color="#f1f5f9" roughness={0.5} metalness={0.1} />
      </mesh>

      {/* Raised Floor Tile Grid Base (Clean Anti-Static Polyurethane Finish) */}
      <mesh position={[0, -0.01, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <planeGeometry args={[28, 22]} />
        <meshStandardMaterial
          color="#e2e8f0"
          roughness={0.25}
          metalness={0.15}
        />
      </mesh>

      {/* COLD AISLE: Clean Chilled Air Plenum Supply (Luminous Sky Blue) */}
      <mesh position={[0, 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.8, 14.5]} />
        <meshBasicMaterial color="#38bdf8" transparent opacity={0.32} />
      </mesh>

      {/* HOT AISLE 1 (Exhaust Row A): Luminous Amber/Coral Thermal Exhaust */}
      <mesh position={[-5.3, 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.6, 14.5]} />
        <meshBasicMaterial color="#fb923c" transparent opacity={0.28} />
      </mesh>

      {/* HOT AISLE 2 (Exhaust Row B): Luminous Amber/Coral Thermal Exhaust */}
      <mesh position={[5.3, 0.015, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.6, 14.5]} />
        <meshBasicMaterial color="#fb923c" transparent opacity={0.28} />
      </mesh>

      {/* Optical Acrylic Cold-Aisle Containment Roof */}
      <mesh position={[0, 4.9, 0]}>
        <boxGeometry args={[4.2, 0.05, 14.0]} />
        <meshPhysicalMaterial
          color="#e0f2fe"
          transparent
          opacity={0.4}
          roughness={0.05}
          metalness={0.1}
          transmission={0.9}
          ior={1.45}
        />
      </mesh>

      {/* Structural Support Columns */}
      {[-13.5, 13.5].map((x, i) =>
        [-9, 0, 9].map((z, j) => (
          <mesh key={`${i}-${j}`} position={[x, 4.5, z]} castShadow receiveShadow>
            <boxGeometry args={[0.8, 9.0, 0.8]} />
            <meshStandardMaterial color="#cbd5e1" roughness={0.3} metalness={0.4} />
          </mesh>
        ))
      )}
    </group>
  );
}

export default function DataCenterModel({
  viewMode = 'telemetry',
  telemetryData,
  mlAnomalyResult,
  selectedAsset,
  onSelectAsset,
  onHoverComponent
}) {
  const rackLayout = useMemo(() => {
    const racks = [];
    const zOffsets = [-5.2, -2.6, 0, 2.6, 5.2];

    // Row A (Facing inward toward Cold Aisle, facing +X)
    zOffsets.forEach((z, idx) => {
      const rackNum = idx + 1;
      const rackId = `RACK-A0${rackNum}`;
      const isMonitoredNode = rackId === 'RACK-A01';

      racks.push({
        id: rackId,
        row: 'A',
        rackNum,
        position: [-2.1, 0, z],
        rotation: [0, Math.PI / 2, 0],
        isMonitoredNode,
        telemetry: telemetryData,
        anomaly: isMonitoredNode ? mlAnomalyResult : null
      });
    });

    // Row B (Facing inward toward Cold Aisle, facing -X)
    zOffsets.forEach((z, idx) => {
      const rackNum = idx + 1;
      const rackId = `RACK-B0${rackNum}`;

      racks.push({
        id: rackId,
        row: 'B',
        rackNum,
        position: [2.1, 0, z],
        rotation: [0, -Math.PI / 2, 0],
        isMonitoredNode: false,
        telemetry: telemetryData,
        anomaly: null
      });
    });

    return racks;
  }, [telemetryData, mlAnomalyResult]);

  return (
    <group name="DataCenterFacility">
      {/* Clean Architectural Structure & Flooring */}
      <StructuralEnclosure />

      {/* Overhead Cable Trays */}
      <CableTray position={[-2.1, 4.7, 0]} length={15} />
      <CableTray position={[2.1, 4.7, 0]} length={15} />

      {/* CRAH Clean Air Handling Units */}
      <CRAHUnit position={[-10.5, 0, -5]} rotation={[0, Math.PI / 2, 0]} />
      <CRAHUnit position={[-10.5, 0, 5]} rotation={[0, Math.PI / 2, 0]} />
      <CRAHUnit position={[10.5, 0, -5]} rotation={[0, -Math.PI / 2, 0]} />
      <CRAHUnit position={[10.5, 0, 5]} rotation={[0, -Math.PI / 2, 0]} />

      {/* Server Racks (42U Enterprise Standard) */}
      {rackLayout.map((rack) => (
        <Rack3D
          key={rack.id}
          id={rack.id}
          row={rack.row}
          rackNum={rack.rackNum}
          position={rack.position}
          rotation={rack.rotation}
          isMonitoredNode={rack.isMonitoredNode}
          telemetryData={rack.telemetry}
          mlAnomalyResult={rack.anomaly}
          viewMode={viewMode}
          selectedAsset={selectedAsset}
          onSelectAsset={onSelectAsset}
          onHoverComponent={onHoverComponent}
        />
      ))}

      {/* Labeled High-Accuracy Telemetry Markers */}
      <SensorMarker3D
        position={[-2.1, 4.3, -5.2]}
        label="M100 NODE 1 (INLET)"
        tempValue={telemetryData?.temp_core_max || 24.8}
        isAnomaly={mlAnomalyResult?.is_anomaly || false}
        viewMode={viewMode}
      />

      <SensorMarker3D
        position={[0, 3.2, 0]}
        label="COLD AISLE PLENUM"
        tempValue={telemetryData?.inlet_temp || 21.0}
        isAnomaly={false}
        viewMode={viewMode}
      />
    </group>
  );
}