/**
 * Backend API Endpoint Definitions
 * Maps frontend services to FastAPI endpoints serving the Marconi-100 digital twin.
 */
export const ENDPOINTS = {
  // Telemetry Ingestion & Stream Endpoints
  TELEMETRY: {
    LATEST: '/data/latest',
    HISTORY: '/data/history',
    STREAM: '/data/stream',
    METRICS: '/data/metrics'
  },

  // Predictive Models & Forecasts
  PREDICTIVE: {
    FORECAST: '/predictive/forecast',
    ANOMALIES: '/predictive/anomalies',
    ANOMALY_LATEST: '/predictive/anomalies/latest',
    RISK: '/predictive/risk',
    METRICS: '/predictive/metrics'
  },

  // Root Cause & Fault Analysis
  ROOT_CAUSE: {
    DIAGNOSE: '/root-cause/diagnose',
    GRAPH: '/root-cause/graph',
    INCIDENTS: '/root-cause/incidents'
  },

  // Telemetry Quality & Reliability Audits
  RELIABILITY: {
    REPORT: '/reliability/report',
    GAPS: '/reliability/gaps',
    DRIFT: '/reliability/drift'
  },

  // Physical & Logical Asset Topology
  ASSETS: {
    LIST: '/assets',
    BY_ID: (id) => `/assets/${id}`,
    RACKS: '/assets/racks',
    BLADES: '/assets/blades'
  },

  // System Health & Pipeline Metadata
  SYSTEM: {
    HEALTH: '/health',
    MODEL_STATUS: '/models/status'
  }
};