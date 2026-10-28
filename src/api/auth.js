import { apiClient, tokenStore } from "./client";

export const authApi = {
  requestOtp: (phone) => apiClient.post("/accounts/otp/request/", { phone }, { skipAuth: true }),

  me: () => apiClient.get("/accounts/me/").then(({ data }) => data),

  verifyOtp: async (phone, code, challengeId) => {
    const { data } = await apiClient.post("/accounts/otp/verify/", { phone, code, challenge_id: challengeId }, { skipAuth: true });
    tokenStore.set(data.access, data.refresh);
    return data.user;
  },

  logout: () => tokenStore.clear(),
};
