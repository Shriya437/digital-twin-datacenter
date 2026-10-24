/**
 * Centralized API Client
 * Native Fetch-based client with Axios-style parameter handling,
 * metadata envelope, and reliable default routing to the FastAPI backend.
 */

// Default to FastAPI backend URL if VITE_API_URL is unset
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

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
      Accept: 'application/json',
      ...options.headers,
    },
    ...options,
  };

  // Ensure leading slash consistency
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${BASE_URL}${cleanEndpoint}`;

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

    // Standardized envelope with data and metadata
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
  /**
   * Supports both flat params `{ node_id: 'node1' }`
   * and Axios-style nested params `{ params: { node_id: 'node1' } }`
   */
  get: (endpoint, optionsOrParams = {}) => {
    const actualParams = optionsOrParams.params ? optionsOrParams.params : optionsOrParams;
    const query = new URLSearchParams();

    Object.entries(actualParams).forEach(([k, v]) => {
      if (v !== undefined && v !== null && k !== 'params') {
        query.append(k, v);
      }
    });

    const queryString = query.toString() ? `?${query.toString()}` : '';
    const cleanEndpoint = endpoint.split('?')[0];

    return request(`${cleanEndpoint}${queryString}`, {
      method: 'GET',
      headers: optionsOrParams.headers || {},
    });
  },

  post: (endpoint, body = {}, options = {}) => {
    return request(endpoint, {
      method: 'POST',
      body: JSON.stringify(body),
      headers: options.headers || {},
    });
  },

  createWebSocket: (path) => {
    const cleanPath = path.startsWith('/') ? path : `/${path}`;

    // Resolve base WS URL from VITE_API_URL or default to localhost:8000
    if (import.meta.env.VITE_API_URL) {
      const url = new URL(import.meta.env.VITE_API_URL);
      const wsProtocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      return new WebSocket(`${wsProtocol}//${url.host}${cleanPath}`);
    }

    // Default to FastAPI backend port
    return new WebSocket(`ws://localhost:8000/api${cleanPath}`);
  },
};

export default apiClient;