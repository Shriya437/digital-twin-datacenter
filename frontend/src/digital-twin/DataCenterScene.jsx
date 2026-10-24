import React, { Suspense, useState, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid, ContactShadows, Environment } from '@react-three/drei';
import * as THREE from 'three';
import DataCenterModel from './DataCenterModel';
import TwinControls from './TwinControls';
import TwinLegend from './TwinLegend';
import TwinTooltip from './TwinTooltip';

export default function DataCenterScene({
  telemetryData,
  mlAnomalyResult,
  selectedAsset,
  onSelectAsset
}) {
  const [viewMode, setViewMode] = useState('telemetry'); // 'telemetry' | 'thermal' | 'anomaly'
  const [hoveredComponent, setHoveredComponent] = useState(null);
  const [pointerCoords, setPointerCoords] = useState({ x: 0, y: 0 });
  const controlsRef = useRef(null);

  // Smooth Camera Reset Presets
  const handleResetCamera = (viewPreset = 'iso') => {
    if (!controlsRef.current) return;
    const controls = controlsRef.current;

    if (viewPreset === 'iso') {
      controls.object.position.set(12, 10, 16);
      controls.target.set(0, 2.5, 0);
    } else if (viewPreset === 'top') {
      controls.object.position.set(0, 22, 0.1);
      controls.target.set(0, 0, 0);
    } else if (viewPreset === 'aisle') {
      controls.object.position.set(0, 2.2, 8.5);
      controls.target.set(0, 2.2, 0);
    }
    controls.update();
  };

  const handlePointerMove = (e) => {
    setPointerCoords({ x: e.clientX, y: e.clientY });
  };

  return (
    <div
      onPointerMove={handlePointerMove}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
        background: 'linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%)',
        overflow: 'hidden',
        userSelect: 'none'
      }}
    >
      {/* Top HUD View Controls */}
      <TwinControls
        activeMode={viewMode}
        onModeChange={setViewMode}
        onResetCamera={handleResetCamera}
      />

      {/* Bottom State Visual Key */}
      <TwinLegend activeMode={viewMode} />

      {/* 2D Interactive Tooltip */}
      <TwinTooltip
        hoveredComponent={hoveredComponent}
        pointerCoords={pointerCoords}
      />

      {/* 3D WebGL Canvas */}
      <Canvas
        shadows
        camera={{ position: [12, 10, 16], fov: 42, near: 0.1, far: 100 }}
        gl={{
          antialias: true,
          powerPreference: 'high-performance',
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.15
        }}
      >
        {/* Balanced Architectural Studio Illumination */}
        <ambientLight intensity={0.9} color="#ffffff" />
        
        {/* Primary Key Sunlight (Clean Crisp Soft Shadows) */}
        <directionalLight
          position={[14, 18, 12]}
          intensity={1.2}
          color="#fffdfa"
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-near={0.5}
          shadow-camera-far={45}
          shadow-camera-left={-15}
          shadow-camera-right={15}
          shadow-camera-top={15}
          shadow-camera-bottom={-15}
          shadow-bias={-0.0001}
        />

        {/* Soft Secondary Fill Light (Sky-tinted bounce) */}
        <directionalLight position={[-12, 12, -10]} intensity={0.5} color="#e0f2fe" />

        {/* Cold-Aisle Dedicated Soft Uplight */}
        <pointLight position={[0, 1.2, 0]} intensity={1.8} distance={10} color="#38bdf8" />

        {/* Hot Aisle Soft Amber Uplights */}
        <pointLight position={[-5.3, 1.5, 0]} intensity={1.5} distance={9} color="#fb923c" />
        <pointLight position={[5.3, 1.5, 0]} intensity={1.5} distance={9} color="#fb923c" />

        {/* Smooth Interaction Controls with Friction/Damping */}
        <OrbitControls
          ref={controlsRef}
          makeDefault
          enableDamping={true}
          dampingFactor={0.06}
          rotateSpeed={0.7}
          panSpeed={0.8}
          zoomSpeed={0.9}
          minDistance={3.5}
          maxDistance={32}
          maxPolarAngle={Math.PI / 2 - 0.04}
          target={[0, 2.5, 0]}
        />

        {/* Clean Architectural Raised Floor Grid */}
        <Grid
          position={[0, 0, 0]}
          args={[30, 30]}
          cellSize={0.6}
          cellThickness={0.8}
          cellColor="#cbd5e1"
          sectionSize={2.4}
          sectionThickness={1.4}
          sectionColor="#94a3b8"
          fadeDistance={30}
          fadeStrength={1.2}
        />

        {/* Soft Contact Shadows on Floor */}
        <ContactShadows
          position={[0, 0.01, 0]}
          opacity={0.45}
          scale={28}
          blur={1.8}
          far={4.5}
        />

        {/* Main Data Center Geometry Model */}
        <Suspense fallback={null}>
          <DataCenterModel
            viewMode={viewMode}
            telemetryData={telemetryData}
            mlAnomalyResult={mlAnomalyResult}
            selectedAsset={selectedAsset}
            onSelectAsset={onSelectAsset}
            onHoverComponent={setHoveredComponent}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}