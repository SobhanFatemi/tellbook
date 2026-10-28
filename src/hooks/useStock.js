import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { stockApi } from "../api/stock";

export function useMyShelf() {
  return useQuery({ queryKey: ["shelf", "mine"], queryFn: stockApi.myShelf });
}

export function useHoldItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (stockItemId) => stockApi.holdItem(stockItemId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shelf", "mine"] }),
  });
}
