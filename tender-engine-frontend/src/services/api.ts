/**
 * Reusable API client for the Tender Engine backend.
 *
 * - Automatically injects JWT Bearer token from localStorage
 * - Handles JSON serialization/deserialization
 * - Provides typed error handling
 * - Uses VITE_API_BASE_URL env var for production API URL
 */

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

console.log('API BASE URL:', API_BASE);

export interface ApiError {
  detail?: string;
  code?: string;
  message?: string;
}

export class ApiRequestError extends Error {
  public status: number;
  public code: string;

  constructor(message: string, status: number, code: string = 'unknown') {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.code = code;
  }
}

const TOKEN_KEY = 'access_token';

function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    console.warn('[API] Failed to store token — localStorage may be full');
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    console.warn('[API] Failed to clear token');
  }
}

export function getStoredToken(): string | null {
  return getToken();
}

/**
 * Decode the payload of a JWT token without verification (client-side only).
 * Returns null if the token is malformed.
 * Useful for checking token expiry before making server calls.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * Check if a JWT token is expired based on its 'exp' claim.
 * Returns true if the token is expired or malformed.
 */
export function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || !payload.exp) return true;
  const expMs = (payload.exp as number) * 1000;
  return Date.now() >= expMs;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  let response: Response;
  try {
    response = await fetch(url, config);
  } catch (err) {
    throw new ApiRequestError(
      'Network error. Please check your connection and ensure the backend server is running.',
      0,
      'network_error',
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      (body as ApiError)?.detail ||
      (body as ApiError)?.message ||
      `Request failed with status ${response.status}`;
    let code = 'request_failed';
    if (response.status === 401) code = 'unauthorized';
    else if (response.status === 422) code = 'validation_error';
    else if (response.status === 409) code = 'conflict';
    else if (response.status === 429) code = 'rate_limit_exceeded';
    else if (response.status >= 500) code = 'server_error';
    throw new ApiRequestError(detail, response.status, code);
  }

  return body as T;
}

// Convenience methods
export const api = {
  get: <T>(endpoint: string) => request<T>(endpoint, { method: 'GET' }),

  post: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: 'POST',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    }),

  put: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: 'PUT',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data?: unknown) =>
    request<T>(endpoint, {
      method: 'PATCH',
      body: data !== undefined ? JSON.stringify(data) : undefined,
    }),

  delete: <T>(endpoint: string) =>
    request<T>(endpoint, { method: 'DELETE' }),
};

export default api;