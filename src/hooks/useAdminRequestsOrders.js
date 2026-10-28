import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { requestsApi } from "../api/requests";

export function useAdminRequests(status) {
  return useQuery({
    queryKey: ["admin", "requests", status],
    queryFn: () => requestsApi.adminListRequests(status),
  });
}

export function useAdminOrders(status) {
  return useQuery({
    queryKey: ["admin", "orders", status],
    queryFn: () => requestsApi.adminListOrders(status),
  });
}

function invalidateAdminQueues(queryClient) {
  queryClient.invalidateQueries({ queryKey: ["admin", "shipments"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "refunds"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "requests"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "dashboard"] });
}

export function useSendQuote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, payload }) => requestsApi.sendQuote(requestId, payload),
    onSuccess: () => invalidateAdminQueues(queryClient),
  });
}

export function useMarkRequestFailed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ requestId, failureReason }) => requestsApi.markRequestFailed(requestId, failureReason),
    onSuccess: () => invalidateAdminQueues(queryClient),
  });
}

export function useStartSourcing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId) => requestsApi.startSourcing(orderId),
    onSuccess: () => invalidateAdminQueues(queryClient),
  });
}

export function useMarkSourced() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, payload }) => requestsApi.markSourced(orderId, payload),
    onSuccess: () => invalidateAdminQueues(queryClient),
  });
}

export function useMarkOrderFailed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, failureReason }) => requestsApi.markOrderFailed(orderId, failureReason),
    onSuccess: () => invalidateAdminQueues(queryClient),
  });
}
