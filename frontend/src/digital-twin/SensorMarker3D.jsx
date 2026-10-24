import React, { useRef, useMemo, useState } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

/**
 * SensorMarker3D Component
 * Renders an animated floating 3D sensor beacon with a billboarded HTML overlay
 * showing real-time temperature, sensor labels, and ML anomaly states.
 */
export default function SensorMarker3D({
  position = [0, 4.0, 0],
  label = 'NODE 1 SENSOR',
  tempValue = 24.8,
  isAnomaly = false,
  viewMode = 'telemetry'
}) {
  const pinRef = useRef();
  const ringRef = useRef();
  const [hovered, setHovered] = useState(false);

  // Derive status colors directly from real thermal thresholds and ML anomaly outputs
  const markerColor = useMemo(() => {
    if (isAnomaly) return '#ef4444'; // Red alert beacon[cite: 1]
    if (tempValue > 40) return '#f59e0b'; // Amber elevated thermal state[cite: 1]
    if (viewMode === 'thermal') {
      // Dynamic thermal gradient[cite: 1]
      return tempValue < 25 ? '#00f2fe' : tempValue < 35 ? '#38bdf8' : '#f97316';
    }
    return '#00f2fe'; // Nominal cyan[cite: 1]
  }, [isAnomaly, tempValue, viewMode]);

  // Floating bob and ring pulse animations
  useFrame(({ clock }) => {
    const elapsed = clock.getElapsedTime();

    // Gentle vertical oscillation
    if (pinRef.current) {
      pinRef.current.position.y = Math.sin(elapsed * 2.5) * 0.08;
    }

    // Expanding pulse ring for anomalies or active hover
    if (ringRef.current) {
      const scale = (elapsed % 1.5) * 1.8 + 0.5;
      ringRef.current.scale.set(scale, scale, 1);
      ringRef.current.material.opacity = Math.max(1.0 - (elapsed % 1.5) / 1.5, 0);
    }
  });

  return (
    <group position={position}>
      {/* Animated 3D Floating Geometry Anchor */}
      <group ref={pinRef}>
        {/* Core Diamond Marker */}
        <mesh
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
        >
          <octahedronGeometry args={[0.16, 0]} />
          <meshBasicMaterial color={markerColor} toneMapped={false} />
        </mesh>

        {/* Vertical Tether Line connecting beacon to equipment surface */}
        <line>
          <bufferGeometry
            attach="geometry"
            onUpdate={(self) => {
              const points = [
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(0, -1.2, 0)
              ];
              self.setFromPoints(points);
            }}
          />
          <lineDashedMaterial
            color={markerColor}
            dashSize={0.08}
            gapSize={0.06}
            transparent
            opacity={0.6}
          />
        </line>

        {/* Animated Radial Shockwave / Pulse Ring */}
        <mesh ref={ringRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]}>
          <ringGeometry args={[0.2, 0.28, 32]} />
          <meshBasicMaterial
            color={markerColor}
            transparent
            opacity={0.8}
            side={THREE.DoubleSide}
            toneMapped={false}
          />
        </mesh>

        {/* In-Scene Omnidirectional Glow */}
        <pointLight
          color={markerColor}
          intensity={isAnomaly ? 1.6 : 0.6}
          distance={2.5}
        />

        {/* Billboarded HTML Data Badge */}
        <Html
          position={[0, 0.38, 0]}
          center
          distanceFactor={18}
          zIndexRange={[100, 0]}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'rgba(11, 19, 43, 0.92)',
              backdropFilter: 'blur(8px)',
              border: `1px solid ${isAnomaly ? 'rgba(239, 68, 68, 0.6)' : 'rgba(56, 189, 248, 0.35)'}`,
              borderRadius: '20px',
              padding: '4px 10px',
              boxShadow: `0 4px 14px rgba(0, 0, 0, 0.6), 0 0 10px ${isAnomaly ? 'rgba(239, 68, 68, 0.4)' : 'rgba(0, 242, 254, 0.2)'}`,
              whiteSpace: 'nowrap',
              pointerEvents: 'none',
              transform: hovered ? 'scale(1.08)' : 'scale(1.0)',
              transition: 'transform 0.15s ease'
            }}
          >
            {/* Glowing Status Dot */}
            <div
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: markerColor,
                boxShadow: `0 0 6px ${markerColor}`
              }}
            />

            {/* Sensor Tag */}
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                color: '#cbd5e1',
                letterSpacing: '0.04em'
              }}
            >
              {label}
            </span>

            {/* Live Numerical Value */}
            <span
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: '#ffffff',
                fontFamily: 'monospace'
              }}
            >
              {typeof tempValue === 'number' ? `${tempValue.toFixed(1)}°C` : tempValue}
            </span>

            {/* Anomaly Flag Tag */}
            {isAnomaly && (
              <span
                style={{
                  backgroundColor: 'rgba(239, 68, 68, 0.25)',
                  color: '#f87171',
                  border: '1px solid rgba(248, 113, 113, 0.4)',
                  borderRadius: '4px',
                  padding: '1px 5px',
                  fontSize: '9px',
                  fontWeight: 700,
                  textTransform: 'uppercase'
                }}
              >
                ANOMALY[cite: 1]
              </span>
            )}
          </div>
        </Html>
      </group>
    </group>
  );
}