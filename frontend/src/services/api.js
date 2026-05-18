import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 120000, // 120s — queries ao Supabase podem levar 60-90s
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("dashboard_token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("dashboard_token");
      localStorage.removeItem("dashboard_user");

      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }

    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      (error.request
        ? "Não foi possível conectar ao servidor"
        : "Erro inesperado na aplicação");

    return Promise.reject(new Error(message));
  }
);

export default api;
