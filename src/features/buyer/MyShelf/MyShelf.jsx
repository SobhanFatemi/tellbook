import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMyShelf } from "../../../hooks/useStock";
import { useShipMyShelf } from "../../../hooks/useFulfillment";
import { useStoreSettings } from "../../../hooks/useStoreSettings";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import DeliveryFields from "../../../components/DeliveryFields";
import { emptyDelivery, deliveryFee, deliveryPayload, deliveryValid } from "../../../utils/delivery";
import PaymentPanel from "../../../components/PaymentPanel";
import { useAuth } from "../../../hooks/useAuth";
import Button from "../../../components/Button";
import { formatNumber, formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { daysRemaining } from "../../../utils/jalali";
import { apiErrorMessage } from "../../../api/client";

export default function MyShelf() {
  const shelf = useMyShelf();
  const { user } = useAuth();
  const [parcel, setParcel] = useState(null);
  const store = useStoreSettings();
  const shipping = useShipMyShelf();

  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 30000); return () => clearInterval(timer); }, []);
  const [selected, setSelected] = useState([]);
  const [choice, setChoice] = useState(() => ({ ...emptyDelivery(), mode: "ship_when_ready" }));
  const [error, setError] = useState("");
  const items = shelf.data || [];
  const chosen = items.filter(item => selected.includes(item.id) && !item.shipment_id && new Date(item.expires_at).getTime() > now);
  const bookCount = chosen.reduce((n, item) => n + (item.book ? 1 : (item.merchandise_data?.contents || []).reduce((sum, c) => sum + (c.book_id ? c.quantity : 0), 0)), 0);
  const fee = deliveryFee(choice, store.data, bookCount);
  const submit = (event) => {
    event.preventDefault(); setError("");
    shipping.mutate({ addressId: choice.addressId !== "new" ? choice.addressId : null, payload: { ...deliveryPayload(choice, fee), delivery_method: choice.mode === "courier" ? "courier" : "postal", stock_item_ids: chosen.map(item => item.id) } }, {
      onSuccess: result => { setParcel(result); setSelected([]); },
      onError: err => { setError(apiErrorMessage(err)); shelf.refetch(); store.refetch(); },
    });
  };
  return <div className="max-w-3xl mx-auto">
    <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
      <h1 className="page-title">قفسه من</h1>
      <Link to="/shipments" className="text-sm text-maroon-600 action-link py-3">پیگیری ارسال‌ها</Link>
    </div>
    <p className="text-ink-600 text-sm mb-6 leading-relaxed">این اقلام پرداخت شده و آماده‌اند. هر پک با تمام محتویاتش یکجا ارسال می‌شود. هر کدام را که می‌خواهید انتخاب کنید و فقط هزینه ارسال همین بسته را بپردازید. باقی اقلام تا پایان مهلت خود روی قفسه می‌مانند.</p>
    {parcel && <section className="surface mb-6"><h2 className="section-title">بسته {toPersianDigits(parcel.id)} ثبت شد</h2><p>هزینه ارسال: {formatToman(parcel.shipping_fee)}</p>{parcel.delivery_method === "courier" ? <p>بسته آماده هماهنگی پیک است. تحویل با نام {parcel.recipient_name} انجام می‌شود.</p> : <PaymentPanel payment={parcel.payment} onUploaded={() => setParcel({ ...parcel, payment: { ...parcel.payment, status: "pending_verification" } })} />}<Link to="/shipments" className="action-link inline-block mt-4">پیگیری بسته</Link></section>}
    <QueryBoundary isLoading={shelf.isLoading} isError={shelf.isError} onRetry={shelf.refetch}>
      {!items.length ? <EmptyState title="قفسه‌ت خالیه" description="خریدهای پرداخت‌شده، بعد از آماده‌شدن اینجا قرار می‌گیرند." /> : <form onSubmit={submit}>
        <fieldset className="mb-6">
          <legend className="font-semibold text-ink-700 mb-3">اقلام این بسته را انتخاب کنید</legend>
          {items.map(item => {
            const remaining = daysRemaining(item.expires_at);
            const expired = new Date(item.expires_at).getTime() <= now;
            return <label key={item.id} className="shelf-choice">
              <input type="checkbox" className="mt-1 w-5 h-5 accent-maroon-600" checked={chosen.some(book => book.id === item.id)}
                disabled={Boolean(item.shipment_id) || expired || shipping.isPending}
                onChange={e => setSelected(e.target.checked ? [...selected, item.id] : selected.filter(id => id !== item.id))} />
              <div className="min-w-0 flex-1">
                <h2 className="font-semibold text-ink-700 break-words">{toPersianDigits(item.title || item.book?.title)}</h2>
                {item.shipment_id ? <p className="text-sm text-dusty-600 mt-1">در درخواست ارسال شماره {toPersianDigits(item.shipment_id)}</p> :
                  <p className={`text-sm mt-1 ${remaining <= 5 ? "text-red-700" : "text-ink-600"}`}>{expired ? "مهلت نگهداری به پایان رسیده است" : `${toPersianDigits(remaining)} روز تا پایان مهلت نگهداری`}</p>}
              </div>
            </label>;
          })}
        </fieldset>
        <QueryBoundary isLoading={store.isLoading} isError={store.isError} onRetry={store.refetch}>
          <DeliveryFields value={choice} onChange={setChoice} store={store.data} bookCount={bookCount} allowShelf={false} disabled={shipping.isPending} />
          <div className="mt-5 bg-cream-200 rounded-xl p-4 space-y-2">
            <p className="text-sm">قلم انتخاب‌شده: {formatNumber(chosen.length)} — هزینه اقلام قبلاً پرداخت شده است.</p>
            <p className="font-semibold text-ink-700">{Number.isFinite(fee) ? `هزینه ارسال این بسته: ${formatToman(fee)}` : "هزینه ارسال هنوز توسط فروشگاه ثبت نشده است."}</p>
            <p className="text-sm text-ink-600">{choice.mode === "courier" ? "هزینه‌ای به تلبوک پرداخت نمی‌کنید؛ هزینه پیک با شماست." : "پس از ثبت، رسید هزینه ارسال را همین‌جا بفرستید."}</p>
          </div>
          {error && <p role="alert" className="text-sm text-red-700 mt-3">{error}</p>}
          <Button type="submit" className="mt-4 w-full sm:w-auto" disabled={!chosen.length || !deliveryValid(choice, store.data, bookCount, user) || shipping.isPending}>
            {shipping.isPending ? "در حال ثبت…" : choice.mode === "courier" ? "ثبت تحویل به پیک" : "ثبت بسته و پرداخت هزینه ارسال"}
          </Button>
        </QueryBoundary>
      </form>}
    </QueryBoundary>
  </div>;
}
