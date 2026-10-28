import { apiClient } from "./client";

export const stockApi = {
  myShelf: () => apiClient.get("/stock/shelf/mine/").then((r) => r.data),
  holdItem: (stockItemId) => apiClient.post(`/stock/${stockItemId}/hold/`).then((r) => r.data),
};
