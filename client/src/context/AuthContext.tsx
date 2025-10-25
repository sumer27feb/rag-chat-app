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
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  loginWithTokens: (access: string, refresh: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthCtx | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    localStorage.getItem("access_token")
  );
  const [refreshToken, setRefreshToken] = useState<string | null>(() =>
    localStorage.getItem("refresh_token")
  );
  const [user, setUser] = useState<User | null>(null);

  // Attach Authorization header globally
  useEffect(() => {
    const id = api.interceptors.request.use((config) => {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers = config.headers ?? {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });
    return () => api.interceptors.request.eject(id);
  }, []);

  const fetchMe = async () => {
    const { data } = await api.get<User>("/auth/me");
    setUser(data);
  };

  // Load user info on mount if tokens exist
  useEffect(() => {
    if (!accessToken || !refreshToken) {
      setUser(null);
      return;
    }

    fetchMe().catch(async (err) => {
      console.warn("Access token invalid or expired, trying refresh...", err);
      try {
        const res = await api.post("/auth/refresh", {
          refresh_token: refreshToken,
        });
        const newAccess = res.data.access_token;
        localStorage.setItem("access_token", newAccess);
        setAccessToken(newAccess);
        await fetchMe();
      } catch {
        console.error("Refresh failed, logging out.");
        logout();
      }
    });
  }, []);

  const loginWithTokens = async (access: string, refresh: string) => {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    setAccessToken(access);
    setRefreshToken(refresh);
    await fetchMe();
  };

  const logout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setAccessToken(null);
    setRefreshToken(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({
      isLoggedIn: !!accessToken && !!user,
      accessToken,
      refreshToken,
      user,
      loginWithTokens,
      logout,
    }),
    [accessToken, refreshToken, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
