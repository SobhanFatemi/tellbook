import { apiClient } from "./client";

export const discountsApi = {
  validate: (code, orderTotal) =>
    apiClient.post("/discounts/validate/", { code, order_total: orderTotal }).then((r) => r.data),

  // --- Admin ---
  list: () => apiClient.get("/discounts/").then((r) => r.data),
  create: (payload) => apiClient.post("/discounts/", payload).then((r) => r.data),
  update: (codeId, payload) => apiClient.patch(`/discounts/${codeId}/`, payload).then((r) => r.data),
  remove: (codeId) => apiClient.delete(`/discounts/${codeId}/`),
};
