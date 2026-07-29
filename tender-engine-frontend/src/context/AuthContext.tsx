import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import type { AuthContextType, User } from '../types/auth';
import * as authService from '../services/auth';
import { clearToken, getStoredToken, isTokenExpired, ApiRequestError } from '../services/api';

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    async function restoreAuth() {
      const token = getStoredToken();
      const refreshToken = authService.getStoredRefreshToken();

      if (!token && !refreshToken) {
        setIsLoading(false);
        return;
      }

      try {
        if (token && !isTokenExpired(token)) {
          const userData = await authService.getCurrentUser();
          if (mountedRef.current) {
            setUser(userData);
            setIsLoading(false);
          }
          return;
        }

        if (refreshToken) {
          const refreshed = await authService.refreshSession(refreshToken);
          if (mountedRef.current) {
            setUser(refreshed.user);
            setIsLoading(false);
          }
          return;
        }

        authService.logout();
        setUser(null);
        setIsLoading(false);
      } catch (err) {
        if (err instanceof ApiRequestError && err.status === 401) {
          authService.logout();
          clearToken();
        }
        if (mountedRef.current) {
          setUser(null);
          setIsLoading(false);
        }
      }
    }

    restoreAuth();

    return () => {
      mountedRef.current = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string, rememberMe = false) => {
    const response = await authService.login({ email, password, remember_me: rememberMe });
    setUser(response.user);
  }, []);

  const register = useCallback(async (payload: { fullName: string; companyName: string; email: string; password: string; confirmPassword: string }) => {
    const response = await authService.register({
      full_name: payload.fullName,
      company_name: payload.companyName,
      email: payload.email,
      password: payload.password,
      confirm_password: payload.confirmPassword,
    });
    setUser(response.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logoutRequest();
    } finally {
      authService.logout();
      setUser(null);
    }
  }, []);

  const logoutAll = useCallback(async () => {
    try {
      await authService.logoutAllRequest();
    } finally {
      authService.logout();
      setUser(null);
    }
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    login,
    register,
    logout,
    logoutAll,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
