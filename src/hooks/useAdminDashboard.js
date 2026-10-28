import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";

const dashboardApi = {
  summary: () => apiClient.get("/admin/dashboard/").then((r) => r.data),
};

export function useAdminDashboard() {
  return useQuery({ queryKey: ["admin", "dashboard"], queryFn: dashboardApi.summary, refetchInterval: 60_000 });
}
