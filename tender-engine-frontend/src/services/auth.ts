import api, { clearToken, setToken } from './api';
import type { User } from '../types/auth';

const REFRESH_TOKEN_KEY = 'refresh_token';

function setRefreshToken(token: string | null): void {
  if (token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface RegisterRequest {
  full_name: string;
  company_name: string;
  email: string;
  password: string;
  confirm_password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string | null;
  token_type: string;
  expires_in: number;
  refresh_expires_in: number | null;
  remember_me: boolean;
  user: User;
}

export async function login(credentials: LoginRequest): Promise<TokenResponse> {
  const data = await api.post<TokenResponse>('/api/auth/login', credentials);
  setToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return data;
}

export async function register(payload: RegisterRequest): Promise<TokenResponse> {
  const data = await api.post<TokenResponse>('/api/auth/register', payload);
  setToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return data;
}

export async function refreshSession(refreshToken: string): Promise<TokenResponse> {
  const data = await api.post<TokenResponse>('/api/auth/refresh', { refresh_token: refreshToken });
  setToken(data.access_token);
  setRefreshToken(data.refresh_token);
  return data;
}

export async function getCurrentUser(): Promise<User> {
  return api.get<User>('/api/auth/me');
}

export async function logoutRequest(): Promise<void> {
  await api.post('/api/auth/logout');
}

export async function logoutAllRequest(): Promise<void> {
  await api.post('/api/auth/logout-all');
}

export function logout(): void {
  clearToken();
  setRefreshToken(null);
}
