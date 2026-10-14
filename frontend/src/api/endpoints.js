/**
 * Documented API endpoints mapping to the FastAPI Python backend.
 */
import { apiClient } from './client';

export const api = {
  // System Health & Overview
  getHealth: () => apiClient.get('/api/health'),
  getOverview: () => apiClient.get('/api/overview'),

  // Digital Twin Visualization & State Estimation
  getRackState: (tickIndex = null) => apiClient.get('/api/digital-twin/rack', { tick_index: tickIndex }),
  getStateEstimation: (limit = 150) => apiClient.get('/api/digital-twin/state-estimation', { limit }),

  // Root-Cause Diagnosis & Topology Graph
  getRootCauses: (limit = 50) => apiClient.get('/api/root-cause/hypotheses', { limit }),
  getDependencyGraph: () => apiClient.get('/api/root-cause/graph'),
  getCorrelations: () => apiClient.get('/api/root-cause/correlations'),

  // Predictive Maintenance
  getPredictiveAssets: () => apiClient.get('/api/predictive-maintenance/assets'),
  getForecasts: () => apiClient.get('/api/predictive-maintenance/forecasts'),

  // Fault Propagation & Cascading Impact
  getFaultImpact: () => apiClient.get('/api/fault-propagation/impact'),
  simulateFault: (faultType, severity = 1.0) =>
    apiClient.post('/api/fault-propagation/simulate', { fault_type: faultType, severity }),

  // Energy Analytics & What-If Simulator
  getEnergyOverview: () => apiClient.get('/api/energy/overview'),
  getEnergyTimeseries: (limit = 200) => apiClient.get('/api/energy/timeseries', { limit }),
  simulateWhatIfEnergy: (reductionPct) =>
    apiClient.post('/api/energy/what-if', { reduction_pct: reductionPct }),

  // Telemetry, Reliability & Anomalies
  getTelemetryHistory: (offset = 0, limit = 200, metric = null) =>
    apiClient.get('/api/telemetry/history', { offset, limit, metric }),
  getReliabilityReport: () => apiClient.get('/api/telemetry/reliability'),
  getAnomalies: (limit = 100) => apiClient.get('/api/telemetry/anomalies', { limit }),

  // Decision Support & Safety Gate
  validateDecisionAction: (payload) => apiClient.post('/api/decision-support/validate', payload),
  getAuditLogs: (limit = 50) => apiClient.get('/api/decision-support/audit-logs', { limit }),
};
