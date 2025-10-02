import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "@/lib/api";

type User = {
  email: string;
  username: string;
  user_id: string;
};

type AuthCtx = {
  isLoggedIn: boolean;
  token: string | null;
  user: User | null;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthCtx | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem("token")
  );
  const [user, setUser] = useState<User | null>(null);

  // Attach/remove Authorization header globally via axios interceptor
  useEffect(() => {
    const id = api.interceptors.request.use((config) => {
      const t = localStorage.getItem("token");
      if (t) {
        config.headers = config.headers ?? {};
        config.headers.Authorization = `Bearer ${t}`;
      }
      return config;
    });
    return () => api.interceptors.request.eject(id);
  }, []);

  const fetchMe = async () => {
    const { data } = await api.get<User>("/auth/me"); // header auto
    setUser(data);
  };

  useEffect(() => {
    if (!token) {
      setUser(null);
      return;
    }
    fetchMe().catch(() => {
      // token invalid/expired
      localStorage.removeItem("token");
      setToken(null);
      setUser(null);
    });
  }, [token]);

  const loginWithToken = async (newToken: string) => {
    localStorage.setItem("token", newToken);
    setToken(newToken); // ✅ important
    await fetchMe(); // safe because interceptor will send header
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({ isLoggedIn: !!token, token, user, loginWithToken, logout }),
    [token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
