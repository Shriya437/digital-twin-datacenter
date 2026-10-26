import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import OverviewDashboard from './views/OverviewDashboard';
import DigitalTwinView from './views/DigitalTwinView';
import RootCauseView from './views/RootCauseView';
import PredictiveMaintenanceView from './views/PredictiveMaintenanceView';
import TelemetryStreamView from './views/TelemetryStreamView';
import FaultPropagationView from './views/FaultPropagationView';
import EnergyAnalyticsView from './views/EnergyAnalyticsView';
import ReliabilityView from './views/ReliabilityView';
import DecisionSupportView from './views/DecisionSupportView';
import { api } from './api/endpoints';

export default function App() {
  const [currentModule, setCurrentModule] = useState('overview');
  const [activeIncidentsCount, setActiveIncidentsCount] = useState(0);

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await api.getOverview();
        setActiveIncidentsCount(res.data?.kpis?.active_anomalies_count || 0);
      } catch (err) {
        console.warn('Backend not yet reachable on initial load:', err.message);
      }
    }
    checkHealth();
  }, []);

  return (
    <div className="app-container">
      <Header activeIncidentsCount={activeIncidentsCount} />
      <div className="main-body">
        <Sidebar
          currentModule={currentModule}
          onSelectModule={(id) => setCurrentModule(id)}
        />
        <main className="content-area">
          {currentModule === 'overview' && (
            <OverviewDashboard onNavigate={setCurrentModule} />
          )}
          {currentModule === 'twin' && (
            <DigitalTwinView />
          )}
          {currentModule === 'root-cause' && (
            <RootCauseView />
          )}
          {currentModule === 'predictive' && (
            <PredictiveMaintenanceView onNavigate={setCurrentModule} />
          )}
          {currentModule === 'telemetry' && (
            <TelemetryStreamView />
          )}
          {currentModule === 'faults' && (
            <FaultPropagationView />
          )}
          {currentModule === 'energy' && (
            <EnergyAnalyticsView />
          )}
          {currentModule === 'reliability' && (
            <ReliabilityView />
          )}
          {currentModule === 'decision' && (
            <DecisionSupportView />
          )}
        </main>
      </div>
    </div>
  );
}
