export interface User {
  id: number;
  email: string;
  full_name: string;
  company_name: string;
  role: string;
  plan: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string | null;
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>;
  register: (payload: {
    fullName: string;
    companyName: string;
    email: string;
    password: string;
    confirmPassword: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  logoutAll: () => Promise<void>;
}
