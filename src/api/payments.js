import { apiClient } from "./client";

export const paymentsApi = {
  uploadById: (paymentId, file) => {
    const form = new FormData();
    form.append("proof_image", file);
    return apiClient.post(`/payments/${paymentId}/upload/`, form).then(r => r.data);
  },
  uploadProof: (orderId, file) => {
    const form = new FormData();
    form.append("proof_image", file);
    return apiClient
      .post(`/payments/${orderId}/proof/`, form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },

  // --- Admin ---
  verificationQueue: () => apiClient.get("/payments/verification-queue/").then((r) => r.data),
  verify: (paymentId, approve, reason = "") =>
    apiClient.post(`/payments/${paymentId}/verify/`, { approve, reason }).then((r) => r.data),
};
