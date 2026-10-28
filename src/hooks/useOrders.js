import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { requestsApi } from "../api/requests";

export function useMyRequests() {
  return useQuery({ queryKey: ["requests", "mine"], queryFn: requestsApi.myRequests });
}

export function useCreateRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: requestsApi.createRequest,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["requests", "mine"] }),
  });
}

export function useMyOrders() {
  return useQuery({ queryKey: ["orders", "mine"], queryFn: requestsApi.myOrders });
}

export function useAcceptQuote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ quoteId, discountCode }) => requestsApi.acceptQuote(quoteId, discountCode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requests", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["orders", "mine"] });
    },
  });
}

export function useBuyEdition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ editionId, discountCode, delivery }) => requestsApi.buyEdition(editionId, discountCode, delivery),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orders", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["books"] });
      queryClient.invalidateQueries({ queryKey: ["shelf", "mine"] });
    },
  });
}
