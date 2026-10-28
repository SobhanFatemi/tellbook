import { apiClient } from "./client";

export const catalogApi = {
  search: (params) => apiClient.get("/catalog/search/", { params }).then((r) => r.data),
  searchFilterOptions: () => apiClient.get("/catalog/search/filters/").then((r) => r.data),
  suggest: (q) => apiClient.get("/catalog/suggest/", { params: { q } }).then((r) => r.data),
  detail: (id) => apiClient.get(`/catalog/${id}/`).then((r) => r.data),
  homepage: () => apiClient.get("/catalog/homepage/").then(r => r.data.books),
  featured: () => apiClient.get("/catalog/featured/").then((r) => r.data),
};
