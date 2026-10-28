import { apiClient } from "./client";

export const refundsApi = {
  list: (status) => apiClient.get("/refunds/", { params: status ? { status } : {} }).then((r) => r.data),
  markProcessed: (refundId, note = "", refund_amount) =>
    apiClient.post(`/refunds/${refundId}/process/`, { note, refund_amount }).then((r) => r.data),
  listPolicies: () => apiClient.get("/refunds/policies/").then((r) => r.data),
  createPolicy: (payload) => apiClient.post("/refunds/policies/", payload).then((r) => r.data),
  updatePolicy: (policyId, payload) => apiClient.patch(`/refunds/policies/${policyId}/`, payload).then((r) => r.data),
};
