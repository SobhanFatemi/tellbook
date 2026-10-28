import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { refundsApi } from "../api/refunds";

export function useAdminRefunds(status) {
  return useQuery({ queryKey: ["admin", "refunds", status], queryFn: () => refundsApi.list(status) });
}

export function useMarkRefundProcessed() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ refundId, note, refund_amount }) => refundsApi.markProcessed(refundId, note, refund_amount),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "refunds"] }),
  });
}

export function useRefundPolicies() {
  return useQuery({ queryKey: ["admin", "refund-policies"], queryFn: refundsApi.listPolicies });
}

export function useUpdateRefundPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ policyId, payload }) => refundsApi.updatePolicy(policyId, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "refund-policies"] }),
  });
}

export function useSaveRefundPolicy() {
  const queryClient = useQueryClient();
  return useMutation({
    // One policy row per reason (reason is unique) -- update if it exists, create if not.
    mutationFn: ({ existing, reason, deduction_percentage }) =>
      existing
        ? refundsApi.updatePolicy(existing.id, { deduction_percentage })
        : refundsApi.createPolicy({ reason, deduction_percentage }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "refund-policies"] }),
  });
}
