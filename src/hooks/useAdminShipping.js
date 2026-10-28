import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { shippingApi } from "../api/shipping";

export function useShipmentQueue() {
  return useQuery({ queryKey: ["admin", "shipment-queue"], queryFn: shippingApi.queue });
}

function invalidateShipments(queryClient) {
  queryClient.invalidateQueries({ queryKey: ["admin", "shipment-queue"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
  queryClient.invalidateQueries({ queryKey: ["admin", "dashboard"] });
}

export function useMarkShipped() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ shipmentId, trackingCode }) => shippingApi.markShipped(shipmentId, trackingCode),
    onSuccess: () => invalidateShipments(queryClient),
  });
}

export function useMarkDelivered() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (shipmentId) => shippingApi.markDelivered(shipmentId),
    onSuccess: () => invalidateShipments(queryClient),
  });
}
