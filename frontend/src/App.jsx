import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import AssetDetailPanel from './components/AssetDetailPanel';
import { apiClient } from './api/client';

// Dedicated Dashboard Views
import OverviewDashboard from './views/OverviewDashboard';
import DigitalTwinView from './views/DigitalTwinView';
import PredictiveMaintenanceView from './views/PredictiveMaintenanceView';
import AnomalyDetectionView from './views/AnomalyDetectionView';
import ForecastingView from './views/ForecastingView';
import RootCauseView from './views/RootCauseView';
import EnergyAnalyticsView from './views/EnergyAnalyticsView';
import ReliabilityView from './views/ReliabilityView';
import TelemetryExplorerView from './views/TelemetryExplorerView';
import ModelPerformanceView from './views/ModelPerformanceView';

export default function App() {
  // Navigation State
  const [activeView, setActiveView] = useState('overview');
  const [backendConnected, setBackendConnected] = useState(false);

  // Selected asset for 3D inspection and side-panel details
  const [selectedAsset, setSelectedAsset] = useState(null);

  // Check backend health/connectivity on startup and interval
  useEffect(() => {
    let isMounted = true;

    async function checkHealth() {
      try {
        await apiClient.get('/data/latest', { params: { node_id: 'node1' } });
        if (isMounted) setBackendConnected(true);
      } catch (err) {
        if (isMounted) setBackendConnected(false);
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 15000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // View Router
  const renderActiveView = () => {
    switch (activeView) {
      case 'overview':
        return (
          <OverviewDashboard
            onNavigateToTwin={() => setActiveView('digital-twin')}
            selectedAsset={selectedAsset}
            onSelectAsset={setSelectedAsset}
          />
        );

      case 'digital-twin':
        return (
          <DigitalTwinView
            selectedAsset={selectedAsset}
            onSelectAsset={setSelectedAsset}
          />
        );

      case 'predictive-maintenance':
        return <PredictiveMaintenanceView />;

      case 'anomaly-detection':
        return <AnomalyDetectionView />;

      case 'forecasting':
        return <ForecastingView />;

      case 'root-cause':
        return <RootCauseView />;

      case 'energy-analytics':
        return <EnergyAnalyticsView />;

      case 'reliability':
        return <ReliabilityView />;

      case 'telemetry-explorer':
        return <TelemetryExplorerView />;

      case 'model-performance':
        return <ModelPerformanceView />;

      default:
        return (
          <OverviewDashboard
            onNavigateToTwin={() => setActiveView('digital-twin')}
            selectedAsset={selectedAsset}
            onSelectAsset={setSelectedAsset}
          />
        );
    }
  };

  return (
    <div className="app-container"
      // style={{
      //   height: '100vh',
      //   width: '100vw',
      //   backgroundColor: '#070d1e',
      //   color: '#f8fafc',
      //   display: 'flex',
      //   flexDirection: 'column',
      //   fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      //   overflow: 'hidden'
      // }}
    >
      {/* Top Application Header */}
      <Header
        activeDataset="m100_node1_digital_twin.csv"
        totalRecords={17280}
        latestTimestamp="2026-10-23 18:30:00 UTC"
        backendConnected={backendConnected}
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Navigation Sidebar */}
        <Sidebar activeView={activeView} onViewChange={setActiveView} />

        {/* Viewport Content Area */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
          <main
            style={{
              flex: 1,
              padding: activeView === 'digital-twin' ? '12px' : '24px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            {renderActiveView()}
          </main>

          {/* Persistent Asset Drawer outside of the full-screen 3D twin view */}
          {selectedAsset && activeView !== 'digital-twin' && (
            <AssetDetailPanel
              selectedAsset={selectedAsset}
              onClose={() => setSelectedAsset(null)}
            />
          )}
        </div>
      </div>
    </div>
  );
}