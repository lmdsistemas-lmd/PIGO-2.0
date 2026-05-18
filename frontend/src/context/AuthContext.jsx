import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { loginRequest, meRequest } from "../services/authService";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("dashboard_user");
    return saved ? JSON.parse(saved) : null;
  });

  const [loadingAuth, setLoadingAuth] = useState(true);

  useEffect(() => {
    async function loadUser() {
      const token = localStorage.getItem("dashboard_token");

      if (!token) {
        setLoadingAuth(false);
        return;
      }

      try {
        const data = await meRequest();
        setUser(data);
        localStorage.setItem("dashboard_user", JSON.stringify(data));
      } catch {
        localStorage.removeItem("dashboard_token");
        localStorage.removeItem("dashboard_user");
        setUser(null);
      } finally {
        setLoadingAuth(false);
      }
    }

    loadUser();
  }, []);

  async function login(cnpj, login, senha) {
    const data = await loginRequest(cnpj, login, senha);

    localStorage.setItem("dashboard_token", data.access_token);
    localStorage.setItem("dashboard_user", JSON.stringify(data.user));

    setUser(data.user);
    return data.user;
  }

  function logout() {
    localStorage.removeItem("dashboard_token");
    localStorage.removeItem("dashboard_user");
    setUser(null);
  }

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: !!user,
      loadingAuth,
      login,
      logout,
    }),
    [user, loadingAuth]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider");
  }

  return context;
}