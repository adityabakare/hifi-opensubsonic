export interface AuthUser {
  username: string;
}

export interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  checkAuth: () => Promise<void>;
  logout: () => Promise<void>;
}
