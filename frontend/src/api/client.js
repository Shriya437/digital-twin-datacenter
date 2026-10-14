/**
 * Centralized API Client
 * Handles requests, response validation, timestamps, and structured error reporting.
 */

const BASE_URL = import.meta.env.VITE_API_URL || '';

export class ApiError extends Error {
  constructor(message, status, details = null, timestamp = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
    this.timestamp = timestamp || new Date().toISOString();
  }
}

/**
 * Base request dispatcher with error catching, validation, and performance timing.
 */
async function request(endpoint, options = {}) {
  const startTime = performance.now();
  const requestTimestamp = new Date().toISOString();

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  const url = `${BASE_URL}${endpoint}`;

  try {
    const response = await fetch(url, config);
    const durationMs = Math.round(performance.now() - startTime);

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = { detail: response.statusText };
      }

      throw new ApiError(
        errorData.detail || errorData.message || `HTTP ${response.status}: Request failed`,
        response.status,
        {
          endpoint,
          durationMs,
          payload: options.body ? JSON.parse(options.body) : null,
          serverError: errorData,
        },
        requestTimestamp
      );
    }

    const data = await response.json();

    // Attach response metadata envelope
    return {
      data,
      meta: {
        endpoint,
        status: response.status,
        durationMs,
        timestamp: requestTimestamp,
      },
    };
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    // Network or browser fetch failures
    const durationMs = Math.round(performance.now() - startTime);
    throw new ApiError(
      err.message || 'Network connection failed. Backend might be offline.',
      0,
      { endpoint, durationMs, originalError: err.toString() },
      requestTimestamp
    );
  }
}

export const apiClient = {
  get: (endpoint, params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) {
        query.append(k, v);
      }
    });
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request(`${endpoint}${queryString}`, { method: 'GET' });
  },

  post: (endpoint, body = {}) => {
    return request(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  },

  createWebSocket: (path) => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}${path}`;
    return new WebSocket(wsUrl);
  },
};
