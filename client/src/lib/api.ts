import axios from "axios";

export const api = axios.create({
  baseURL: "http://127.0.0.1:8001",
  withCredentials: false,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      // optional: window.location.href = "/";
    }
    return Promise.reject(err);
  }
);
