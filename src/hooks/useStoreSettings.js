import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export function useStoreSettings() {
  return useQuery({ queryKey: ["store-settings"], queryFn: () => apiClient.get("/store/").then(r => r.data), staleTime: 60000 });
}

export function useSaveStoreSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (data) => apiClient.patch("/admin/store-settings/", data).then(r => r.data),
    onSuccess: (data) => client.setQueryData(["store-settings"], data),
  });
}
