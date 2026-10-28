import { useState } from "react";
import { useShipmentQueue, useMarkShipped, useMarkDelivered } from "../../../hooks/useAdminShipping";
import { EmptyState, StatusBadge, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button, { ButtonLink } from "../../../components/Button";
import { Input } from "../../../components/FormFields";
import { apiErrorMessage } from "../../../api/client";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";

export default function AdminShipments() {
  const query = useShipmentQueue();
  return <div>
    <h1 className="page-title">مدیریت ارسال‌ها</h1>
    <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>
      {!query.data?.length ? <EmptyState title="ارسال فعالی نیست" /> : <div className="space-y-4">{query.data.map(shipment => <ShipmentCard key={shipment.id} shipment={shipment} />)}</div>}
    </QueryBoundary>
  </div>;
}

function ShipmentCard({ shipment }) {
  const markShipped = useMarkShipped();
  const markDelivered = useMarkDelivered();
  const [trackingCode, setTrackingCode] = useState("");
  const [error, setError] = useState("");
  const onError = err => setError(apiErrorMessage(err));
  return <Card className="admin-record">
    <header className="admin-record-heading"><div><h2>بسته {toPersianDigits(shipment.id)}</h2><p>{shipment.delivery_method === "courier" ? "تحویل به پیک خریدار" : "ارسال پستی"}</p></div><StatusBadge status={shipment.status} /></header>
    <div className="admin-record-grid">
      <section><h3>اطلاعات گیرنده</h3><dl className="record-facts"><div><dt>نام گیرنده</dt><dd>{shipment.recipient_name}</dd></div><div><dt>تلفن تماس</dt><dd><bdi>{toPersianDigits(shipment.recipient_phone)}</bdi></dd></div>{shipment.delivery_method !== "courier" && <><div><dt>نشانی</dt><dd>{shipment.province}، {shipment.city}، {shipment.address_line}</dd></div><div><dt>کد پستی</dt><dd><bdi>{toPersianDigits(shipment.postal_code)}</bdi></dd></div></>}</dl>{shipment.delivery_method === "courier" && <p className="record-note">هماهنگی پیک با خریدار است؛ تحویل فقط با نام صاحب سفارش.</p>}</section>
      <section><h3>محتویات و هزینه ارسال</h3>{shipment.items.length ? <ul className="shipment-contents">{shipment.items.map(item => <li key={item.id}>{toPersianDigits(item.title)}</li>)}</ul> : <p className="record-note">اقلام پس از آماده‌شدن به بسته اضافه می‌شوند.</p>}<dl className="record-facts"><div><dt>هزینه ارسال ثبت‌شده</dt><dd>{formatToman(shipment.shipping_fee)}</dd></div></dl>
      {shipment.status === "awaiting_payment" && <div className="record-note"><p>{shipment.payment?.status === "pending_verification" ? "رسید منتظر بررسی است." : "منتظر رسید پرداخت خریدار؛ ارسال هنوز مجاز نیست."}</p><ButtonLink variant="secondary" to="/admin/orders#shipping-payments">مشاهده سفارش‌ها و پرداخت</ButtonLink></div>}
      {shipment.status === "waiting_books" && <p className="record-note">پرداخت تأیید شده؛ منتظر آماده‌شدن اقلام.</p>}</section>
    </div>
    {shipment.status === "preparing" && shipment.payment?.status === "verified" && <form className="admin-record-footer record-dispatch-form" onSubmit={e => {
      e.preventDefault(); setError(""); markShipped.mutate({ shipmentId: shipment.id, trackingCode }, { onError });
    }}>
      <div className="flex-1"><Input label={shipment.delivery_method === "courier" ? "کد پیگیری پیک / تحویل" : "کد رهگیری پستی"} localizeDigits value={trackingCode} onChange={e => setTrackingCode(e.target.value)} required dir="ltr" /></div>
      <Button type="submit" disabled={markShipped.isPending}>ثبت ارسال</Button>
    </form>}
    {shipment.status === "shipped" && <div className="admin-record-footer record-dispatch-form"><p className="text-sm">کد رهگیری: <bdi>{toPersianDigits(shipment.tracking_code)}</bdi></p>
      <Button disabled={markDelivered.isPending} onClick={() => { setError(""); markDelivered.mutate(shipment.id, { onError }); }}>تایید تحویل به مشتری</Button>
    </div>}
    {error && <p role="alert" className="text-sm text-red-700 mt-3">{error}</p>}
  </Card>;
}
