import { apiClient } from "./client";

export const requestsApi = {
  myRequests: () => apiClient.get("/orders/requests/mine/").then((r) => r.data),

  // FormData when a reference_image is attached, plain object otherwise.
  createRequest: (payload) => {
    const hasFile = payload.reference_image instanceof File;
    if (!hasFile) return apiClient.post("/orders/requests/", payload).then((r) => r.data);

    const form = new FormData();
    Object.entries(payload).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") form.append(key, value);
    });
    return apiClient
      .post("/orders/requests/", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },

  acceptQuote: (quoteId, discountCode = "") =>
    apiClient.post(`/orders/quotes/${quoteId}/accept/`, { discount_code: discountCode }).then((r) => r.data),

  myOrders: () => apiClient.get("/orders/mine/").then((r) => r.data),

  buyEdition: (editionId, discountCode = "", delivery = {}) =>
    apiClient.post(`/orders/buy/edition/${editionId}/`, { discount_code: discountCode, ...delivery }).then((r) => r.data),

  // --- Admin (creator-only) ---
  adminListRequests: (status) =>
    apiClient.get("/orders/requests/all/", { params: status ? { status } : {} }).then((r) => r.data),

  adminListOrders: (status) =>
    apiClient.get("/orders/all/", { params: status ? { status } : {} }).then((r) => r.data),

  sendQuote: (requestId, payload) =>
    apiClient.post(`/orders/requests/${requestId}/quote/`, payload).then((r) => r.data),

  markRequestFailed: (requestId, failureReason) =>
    apiClient.post(`/orders/requests/${requestId}/fail/`, { failure_reason: failureReason }).then((r) => r.data),

  startSourcing: (orderId) => apiClient.post(`/orders/${orderId}/start-sourcing/`).then((r) => r.data),

  markOrderFailed: (orderId, failureReason) =>
    apiClient.post(`/orders/${orderId}/fail/`, { failure_reason: failureReason }).then((r) => r.data),

  markSourced: (orderId, payload) =>
    apiClient.post(`/orders/${orderId}/mark-sourced/`, payload).then((r) => r.data),
};
