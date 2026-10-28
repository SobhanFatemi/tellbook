import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
export function useAdminCatalog(params) {
  return useQuery({queryKey:["admin","catalog",params],queryFn:()=>apiClient.get("/catalog/admin/books/",{params}).then(r=>r.data)});
}
export function usePublishers() {
  return useQuery({queryKey:["admin","publishers"],queryFn:()=>apiClient.get("/publishers/").then(r=>r.data)});
}
export function useCatalogMutation(mutationFn, onSuccess) {
  const client=useQueryClient();
  return useMutation({mutationFn,onSuccess:data=>{client.invalidateQueries({queryKey:["admin"]});client.invalidateQueries({queryKey:["books"]});onSuccess?.(data);}});
}
