import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { paymentsApi } from "../api/payments";
import { shippingApi } from "../api/shipping";
import { discountsApi } from "../api/discounts";

export function useUploadPaymentProof() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, file }) => paymentsApi.uploadProof(orderId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["orders", "mine"] }),
  });
}

export function useMyAddresses(enabled = true) {
  return useQuery({ queryKey: ["addresses", "mine"], queryFn: shippingApi.myAddresses, enabled });
}

export function useAddAddress() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: shippingApi.addAddress,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["addresses", "mine"] }),
  });
}

export function useShipMyShelf() {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ addressId, payload }) => shippingApi.shipMyShelf(addressId, payload),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["shelf"] }); client.invalidateQueries({ queryKey: ["shipments"] }); },
  });
}

/** Not a query -- called imperatively as the buyer types/confirms a code. */
export function validateDiscountCode(code, orderTotal) {
  return discountsApi.validate(code, orderTotal);
}
