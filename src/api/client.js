import { localizedApiError } from "../utils/apiMessages";
import axios from "axios";

// Set VITE_API_BASE_URL in a .env file (see .env.example). Defaults to the
// local Django dev server.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

// Private staging keeps HTTP Basic credentials at the edge and app JWTs separate.
const AUTH_HEADER = import.meta.env.VITE_AUTH_HEADER || "Authorization";

const ACCESS_KEY = "tellbook_access";
const REFRESH_KEY = "tellbook_refresh";

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem("tellbook_user");
  },
};

export const apiClient = axios.create({ baseURL: BASE_URL, timeout: 20000 });

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token && !config.skipAuth) config.headers[AUTH_HEADER] = `Bearer ${token}`;
  return config;
});

let refreshPromise = null;

async function refreshAccessToken() {
  const refresh = tokenStore.getRefresh();
  if (!refresh) throw new Error("No refresh token");
  try {
    const { data } = await axios.post(`${BASE_URL}/accounts/token/refresh/`, { refresh }, { timeout: 20000 });
    if (tokenStore.getRefresh() !== refresh) throw new Error("Session changed");
    tokenStore.set(data.access, refresh);
    return data.access;
  } catch (error) {
    if (tokenStore.getRefresh() !== refresh) error.sessionChanged = true;
    throw error;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original.skipAuth && !original._retry && tokenStore.getRefresh()) {
      original._retry = true;
      try {
        refreshPromise = refreshPromise || refreshAccessToken();
        const newAccess = await refreshPromise;
        refreshPromise = null;
        original.headers[AUTH_HEADER] = `Bearer ${newAccess}`;
        return apiClient(original);
      } catch (refreshError) {
        refreshPromise = null;
        if (refreshError.sessionChanged) return Promise.reject(refreshError);
        tokenStore.clear();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

/** Pulls a friendly message out of a DRF error response for display. */
export function apiErrorMessage(error, fallback) {
  return localizedApiError(error, fallback);
}
