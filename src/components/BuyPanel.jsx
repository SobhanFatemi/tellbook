import { useState } from "react";
import Button from "./Button";
import DiscountCodeField from "./DiscountCodeField";
import { formatToman } from "../utils/persianFormat";
import { Spinner } from "./Feedback";
import { useStoreSettings } from "../hooks/useStoreSettings";
import { useAuth } from "../hooks/useAuth";
import DeliveryFields from "./DeliveryFields";
import { emptyDelivery, deliveryFee, deliveryPayload, deliveryValid } from "../utils/delivery";

export default function BuyPanel({ baseTotal, onConfirm, isSubmitting, confirmLabel = "تایید و ادامه", allowDelivery = false, bookCount = 1, deliveryChoice, onDeliveryChange }) {
  const [discount, setDiscount] = useState({ code: "", amount: 0 });
  const [localChoice, setLocalChoice] = useState(emptyDelivery);
  const choice = deliveryChoice || localChoice;
  const setChoice = onDeliveryChange || setLocalChoice;
  const { user, isAuthenticated } = useAuth();
  const store = useStoreSettings();
  const fee = deliveryFee(choice, store.data, bookCount);
  const total = Number(baseTotal) - discount.amount + (Number.isFinite(fee) ? fee : 0);
  return <div className="border-t border-cream-300 mt-6 pt-6 flex flex-col gap-5">
    {allowDelivery && <DeliveryFields value={choice} onChange={setChoice} store={store.data} bookCount={bookCount} disabled={isSubmitting} />}
    {allowDelivery && store.isError && <p role="alert">تنظیمات ارسال دریافت نشد. <Button variant="ghost" onClick={() => store.refetch()}>تلاش دوباره</Button></p>}
    <DiscountCodeField orderTotal={baseTotal} onApplied={(code, amount) => setDiscount({ code, amount })} />
    <dl className="space-y-3 text-sm" aria-live="polite"><div className="flex justify-between gap-3"><dt>جمع اقلام</dt><dd>{formatToman(baseTotal)}</dd></div>{discount.amount > 0 && <div className="flex justify-between gap-3"><dt>تخفیف</dt><dd>{formatToman(discount.amount)}</dd></div>}<div className="flex justify-between gap-3"><dt>هزینه ارسال</dt><dd>{choice.mode === "shelf" ? "هنگام درخواست ارسال محاسبه می‌شود" : Number.isFinite(fee) ? formatToman(fee) : "در حال دریافت…"}</dd></div><div className="flex justify-between gap-3 font-bold text-base pt-3"><dt>مبلغ قابل پرداخت</dt><dd>{formatToman(total)}</dd></div></dl>
    <Button onClick={() => onConfirm(discount.code, deliveryPayload(choice, fee))} disabled={isSubmitting || (allowDelivery && (!isAuthenticated || !deliveryValid(choice, store.data, bookCount, user) || (choice.mode !== 'shelf' && (store.isLoading || store.isError))))}>{isSubmitting ? <Spinner className="w-4 h-4 mx-auto" /> : confirmLabel}</Button>
  </div>;
}
