import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { discountsApi } from "../api/discounts";

export function useAdminDiscounts() {
  return useQuery({ queryKey: ["admin", "discounts"], queryFn: discountsApi.list });
}

function useDiscountMutation(fn) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "discounts"] }),
  });
}

export const useCreateDiscount = () => useDiscountMutation(discountsApi.create);
export const useUpdateDiscount = () => useDiscountMutation(({ id, payload }) => discountsApi.update(id, payload));
export const useDeleteDiscount = () => useDiscountMutation(discountsApi.remove);
