import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentsApi } from "../api/payments";

export function usePaymentVerificationQueue() {
  return useQuery({ queryKey: ["admin", "payment-queue"], queryFn: paymentsApi.verificationQueue });
}

export function useVerifyPayment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ paymentId, approve, reason }) => paymentsApi.verify(paymentId, approve, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "payment-queue"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "shipment-queue"] });
      queryClient.invalidateQueries({ queryKey: ["shipments"] });
      queryClient.invalidateQueries({ queryKey: ["shelf"] });
    },
  });
}
