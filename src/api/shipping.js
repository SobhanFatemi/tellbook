import { apiClient } from "./client";

export const shippingApi = {
  myAddresses: () => apiClient.get("/shipping/addresses/").then((r) => r.data),
  addAddress: (payload) => apiClient.post("/shipping/addresses/", payload).then((r) => r.data),
  shipMyShelf: (addressId, payload) => apiClient.post(addressId ? `/shipping/ship-shelf/${addressId}/` : "/shipping/ship-shelf/", payload).then((r) => r.data),

  mine: () => apiClient.get("/shipping/mine/").then(r => r.data),
  cancel: (id) => apiClient.post(`/shipping/${id}/cancel/`).then(r => r.data),

  // --- Admin ---
  queue: () => apiClient.get("/shipping/queue/").then((r) => r.data),
  markShipped: (shipmentId, trackingCode) =>
    apiClient.post(`/shipping/${shipmentId}/mark-shipped/`, { tracking_code: trackingCode }).then((r) => r.data),
  markDelivered: (shipmentId) => apiClient.post(`/shipping/${shipmentId}/mark-delivered/`).then((r) => r.data),
};
