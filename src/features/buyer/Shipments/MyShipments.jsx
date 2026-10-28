import { useRef, useState } from "react";
import { Copy, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { shippingApi } from "../../../api/shipping";
import { apiErrorMessage } from "../../../api/client";
import { QueryBoundary, EmptyState, StatusBadge } from "../../../components/Feedback";
import PaymentPanel from "../../../components/PaymentPanel";
import Card from "../../../components/Card";
import Button, { ButtonLink } from "../../../components/Button";
import { formatToman, toEnglishDigits, toPersianDigits } from "../../../utils/persianFormat";

export default function MyShipments() {
  const query = useQuery({ queryKey: ["shipments", "mine"], queryFn: shippingApi.mine });
  return <div className="max-w-3xl mx-auto">
    <h1 className="page-title">ارسال‌های من</h1>
    <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>
      {!query.data?.length ? <EmptyState title="هنوز درخواست ارسالی نداری" description="کتاب‌های آماده را از قفسه انتخاب کن." action={<Link className="action-link text-maroon-600" to="/shelf">رفتن به قفسه</Link>} /> :
        <div className="space-y-4">{query.data.map(shipment => <ShipmentCard key={shipment.id} shipment={shipment} />)}</div>}
    </QueryBoundary>
  </div>;
}

function ShipmentCard({ shipment }) {
  const [error, setError] = useState("");
  const client = useQueryClient();
  const cancel = useMutation({ mutationFn: () => shippingApi.cancel(shipment.id),
    onSuccess: () => { client.invalidateQueries({ queryKey: ["shipments"] }); client.invalidateQueries({ queryKey: ["shelf"] }); },
    onError: err => setError(apiErrorMessage(err)),
  });
  const canCancel = shipment.status === "awaiting_payment" && !shipment.payment?.order_id && ["pending_proof", "rejected"].includes(shipment.payment?.status);
  return <Card>
    <div className="flex flex-wrap justify-between items-start gap-2 mb-3"><h2 className="font-semibold text-ink-700">بسته شماره {toPersianDigits(shipment.id)}</h2><StatusBadge status={shipment.status} /></div>
    {!!shipment.items.length && <ul className="list-disc list-inside text-sm mb-3">{shipment.items.map(item => <li key={item.id}>{toPersianDigits(item.title)}</li>)}</ul>}
    <p className="text-sm text-ink-600">{shipment.delivery_method === "courier" ? `پیک خریدار — تحویل به نام ${shipment.recipient_name}` : `${shipment.recipient_name}، ${shipment.province}، ${shipment.city}، ${shipment.address_line}`}</p>
    <p className="text-sm mt-2">هزینه ارسال: {formatToman(shipment.shipping_fee)}</p>
    {shipment.tracking_code && <ShipmentTracking code={shipment.tracking_code} postal={shipment.delivery_method !== "courier"} />}
    {shipment.payment?.order_id && <section className="buyer-order-progress"><div className="buyer-order-progress-heading"><h3>وضعیت تهیه و ارسال</h3><ButtonLink to="/orders" variant="secondary">پیگیری وضعیت سفارش</ButtonLink></div></section>}

    {shipment.status === "waiting_books" && <p className="text-sm mt-3 text-ink-600">هزینه ارسال پرداخت شده؛ پس از آماده‌شدن کتاب، بسته ارسال می‌شود.</p>}
    {shipment.status === "awaiting_payment" && <PaymentPanel payment={shipment.payment} />}
    {canCancel && <Button variant="ghost" className="mt-4" disabled={cancel.isPending} onClick={() => cancel.mutate()}>لغو درخواست ارسال و نگه‌داشتن کتاب‌ها روی قفسه</Button>}
    {error && <p role="alert" className="text-red-700 text-sm mt-2">{error}</p>}
  </Card>;
}

function ShipmentTracking({ code, postal }) {
  const [message, setMessage] = useState("");
  const field = useRef(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(toEnglishDigits(String(code)));
      setMessage("کد رهگیری کپی شد.");
    } catch {
      field.current?.focus();
      field.current?.select();
      setMessage("کپی خودکار ممکن نشد؛ کد را از کادر انتخاب و کپی کنید.");
    }
  };
  return <section className="shipment-tracking" aria-label="رهگیری مرسوله">
    <label className="shipment-tracking-code"><span>کد رهگیری</span><input ref={field} readOnly dir="ltr" aria-label="کد رهگیری" value={toPersianDigits(code)} onFocus={event => event.target.select()} /></label>
    <div className="shipment-tracking-actions">
      <Button variant="ghost" onClick={copy}><Copy size={17} aria-hidden="true" />کپی کد</Button>
      {postal && <a className="button button--secondary" href="https://tracking.post.ir/" target="_blank" rel="noopener noreferrer">رهگیری در سایت پست<ExternalLink size={17} aria-hidden="true" /><span className="sr-only"> (در زبانه جدید)</span></a>}
    </div>
    <p className="shipment-tracking-help" role="status">{message || (postal ? "کد را کپی کنید و در سایت پست وارد کنید." : "برای پیگیری، کد را در اختیار پشتیبانی قرار دهید.")}</p>
  </section>;
}
