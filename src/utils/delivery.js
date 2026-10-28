export const emptyDelivery = () => ({ mode: "shelf", addressId: "", address: { full_name: "", phone: "", province: "", city: "", address_line: "", postal_code: "" }, collector_name: "" });
export const deliveryFee = (choice, store, count) => choice.mode === "ship_when_ready" ? Number(count <= 6 ? store?.shipping_fee : store?.shipping_fee_over_six) : 0;
export const deliveryPayload = (choice, fee) => ({ delivery_mode: choice.mode, ...(choice.mode !== "shelf" ? { expected_shipping_fee: String(fee) } : {}), ...(choice.mode === "courier" ? { collector_name: choice.collector_name } : choice.mode === "ship_when_ready" ? choice.addressId && choice.addressId !== "new" ? { address_id: Number(choice.addressId) } : { address: choice.address } : {}) });
export function deliveryValid(choice, store, count, user) {
  if (choice.mode === "shelf") return true;
  if (choice.mode === "courier") return Boolean(user?.full_name?.trim() || choice.collector_name.trim());
  if (!(deliveryFee(choice, store, count) > 0)) return false;
  if (choice.addressId && choice.addressId !== "new") return true;
  return Object.values(choice.address).every(v => v.trim()) && /^09\d{9}$/.test(choice.address.phone) && /^\d{10}$/.test(choice.address.postal_code);
}
