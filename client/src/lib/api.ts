import axios from "axios";

export const api = axios.create({
  // ✅ Use relative URL — works with Nginx proxy (both local + prod)
  baseURL: "/api",
  withCredentials: false,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem("refresh_token");

      if (refreshToken) {
        try {
          // ✅ Relative path again — Nginx will forward this correctly
          const res = await axios.post("/api/auth/refresh", {
            refresh_token: refreshToken,
          });
          const newAccessToken = res.data.access_token;
          localStorage.setItem("access_token", newAccessToken);

          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          return api(originalRequest);
        } catch (err) {
          console.error("Refresh token invalid or expired", err);
          localStorage.clear();
          window.location.href = "/";
        }
      }
    }

    return Promise.reject(error);
  }
);

export default api;
