import { groupOrderItems } from "../../../utils/orderItems";
import { usePaymentVerificationQueue } from "../../../hooks/useAdminPayments";
import { apiClient } from "../../../api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAdminOrders, useStartSourcing, useMarkSourced, useMarkOrderFailed } from "../../../hooks/useAdminRequestsOrders";
import { EmptyState, StatusBadge, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import PaymentReview from "../../../components/PaymentReview";
import Tabs from "../../../components/Tabs";
import { Select, Textarea } from "../../../components/FormFields";
import { formatNumber, formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";
import { apiErrorMessage } from "../../../api/client";

const TABS = [
  { value: "", label: "همه" },
  { value: "awaiting_payment", label: "منتظر پرداخت" },
  { value: "paid", label: "پرداخت شده" },
  { value: "sourcing", label: "در حال تهیه" },
  { value: "stock_ready", label: "آماده ارسال" },
  { value: "shipped", label: "ارسال شده" },
  { value: "failed", label: "تهیه ناموفق" },
  { value: "cancelled", label: "لغو شده" },
  { value: "refunded", label: "بازگشت وجه" },
];

export default function AdminOrders() {
  const [searchParams, setSearchParams] = useSearchParams();
  const payments = usePaymentVerificationQueue();
  const status = searchParams.get("status") || "";
  const { data: orders, isLoading, isError, refetch } = useAdminOrders(status);

  return (
    <div>
      <h1 className="page-title">سفارش‌ها و پرداخت</h1>
      <section id="shipping-payments" className="shipping-payment-queue">
        <QueryBoundary isLoading={payments.isLoading} isError={payments.isError} onRetry={payments.refetch}>
          {payments.data?.filter(p => !p.order_id).map(p => <Card key={p.id} className="admin-order-card"><div className="admin-order-heading"><h2>رسید ارسال بسته {toPersianDigits(p.shipment_id)}</h2><span>پرداخت ارسال از قفسه</span></div><PaymentReview payment={p} /></Card>)}
        </QueryBoundary>
      </section>
      <div className="admin-orders-tabs"><Tabs tabs={TABS} active={status} onChange={(value) => setSearchParams(value ? { status: value } : {})} /></div>
      <div className="admin-orders-filter"><Select label="وضعیت سفارش" value={status} onChange={e => setSearchParams(e.target.value ? { status: e.target.value } : {})}>{TABS.map(tab => <option key={tab.value} value={tab.value}>{tab.label}</option>)}</Select></div>

      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!orders?.length ? (
        <EmptyState title="سفارشی نیست" />
      ) : (
        <div className="flex flex-col gap-4">
          {orders.map((order) => (
            <OrderCard key={order.id} order={order} />
          ))}
        </div>
      )}
      </QueryBoundary>
    </div>
  );
}

function OrderCard({ order }) {
  const groups = groupOrderItems(order.items);
  const client = useQueryClient();
  const fulfill = useMutation({ mutationFn: indices => apiClient.post(`/products/admin/orders/${order.id}/ready/`, { indices }), onSuccess: () => client.invalidateQueries(), onError: err => setError(apiErrorMessage(err)) });
  const startSourcing = useStartSourcing();
  const markSourced = useMarkSourced();
  const markFailed = useMarkOrderFailed();
  const [failureReason, setFailureReason] = useState("");
  const [showFailure, setShowFailure] = useState(false);
  const [showSourceForm, setShowSourceForm] = useState(false);
  const [error, setError] = useState("");

  const handleStartSourcing = () => {
    setError("");
    startSourcing.mutate(order.id, { onError: (err) => setError(apiErrorMessage(err)) });
  };

  const submitSourced = (e) => {
    e.preventDefault();
    setError("");
    markSourced.mutate(
      { orderId: order.id, payload: {} },
      {
        onSuccess: () => setShowSourceForm(false),
        onError: (err) => setError(apiErrorMessage(err)),
      }
    );
  };

  return (
    <Card className="admin-order-card">
      <div className="admin-order-heading">
        <div>
          <h2>سفارش {toPersianDigits(order.id)}</h2>
          <div className="admin-order-meta"><span>خریدار: <bdi dir="ltr">{toPersianDigits(order.buyer_phone)}</bdi></span><time dateTime={order.created_at}>{formatJalaliShort(order.created_at)}</time></div>
        </div>
        <StatusBadge status={order.status} />
      </div>

      <div className="admin-order-details">
        <section className="admin-order-items"><h3>اقلام سفارش</h3>
          {groups.length > 0 ? <ul>{groups.map(item => <li key={item.key}>
            <div className="admin-order-item-price"><strong>{toPersianDigits(item.title)} <span className="order-quantity" dir="ltr">×{formatNumber(item.quantity)}</span></strong><span>{formatToman(item.total)}</span></div>
            {item.quantity > 1 && item.uniformPrice && <p className="order-unit-price">قیمت هر عدد: {formatToman(item.price)}</p>}
            {(item.contents.length > 1 || item.contents.some(c => c.quantity > 1 || c.title !== item.title)) && <ul className="admin-order-contents">{item.contents.map((c, j) => <li key={j}>{formatNumber(c.quantity)} × {toPersianDigits(c.title)}</li>)}</ul>}
            {item.pendingIndices.length > 0 && ["paid", "sourcing"].includes(order.status) && <div className="order-item-ready"><span>پس از دریافت تمام {formatNumber(item.pendingIndices.length)} عدد تأیید کنید.</span><Button disabled={fulfill.isPending} onClick={() => { setError(""); fulfill.mutate(item.pendingIndices); }}>{item.pendingIndices.length > 1 ? `هر ${formatNumber(item.pendingIndices.length)} عدد آماده شد` : "آماده شد"}</Button></div>}
            {item.readyCount > 0 && <p className="order-ready-note">{formatNumber(item.readyCount)} عدد آماده شده</p>}
          </li>)}</ul> : <p>{toPersianDigits(order.quote?.book_title || "سفارش کتاب")}</p>}
        </section>
        <dl className="admin-order-amounts">
          <div><dt>جمع اقلام</dt><dd>{formatToman(order.total_price)}</dd></div>
          <div><dt>هزینه ارسال</dt><dd>{order.delivery?.mode === "shelf" ? "هنگام درخواست ارسال محاسبه می‌شود" : formatToman(order.delivery?.shipping_fee || 0)}</dd></div>
          <div className="admin-order-total"><dt>مبلغ کل پرداخت</dt><dd>{formatToman(order.payment?.amount_expected ?? order.total_price)}</dd></div>
        </dl>
      </div>
      <PaymentReview payment={order.payment} />
      {["paid", "sourcing"].includes(order.status) && <section className="admin-order-actions" aria-label="عملیات تهیه سفارش">
        <h3>آماده‌سازی سفارش</h3>
        {order.items?.length > 0 && <p>آماده‌بودن را در ردیف هر کالا ثبت کنید؛ برای پک، تمام محتویات باید آماده باشد. مهلت نگهداری ۳۰روزه از تأیید آغاز می‌شود.</p>}
        <div className="admin-order-action-grid">
          {order.status === "paid" && <Button variant="secondary" onClick={handleStartSourcing} disabled={startSourcing.isPending}>شروع تهیه سفارش</Button>}
          {!order.items?.length && <Button variant="secondary" onClick={() => setShowSourceForm(true)}>کتاب دریافت شد — ثبت آماده‌بودن</Button>}
          <Button variant="danger" onClick={() => setShowFailure(true)}>تهیه سفارش ممکن نیست</Button>
        </div>
        {!order.items?.length && showSourceForm && <form onSubmit={submitSourced} className="admin-order-action-form">
          <p>پس از تأیید، کتاب آماده و مهلت نگهداری ۳۰روزه آغاز می‌شود. این کار به‌معنای ارسال بسته نیست؛ ارسال نیاز به پرداخت هزینه ارسال دارد.</p>
          <Button type="submit" disabled={markSourced.isPending}>تأیید آماده‌بودن کتاب</Button>
        </form>}
        {showFailure && <form className="admin-order-action-form" onSubmit={event => {
          event.preventDefault(); setError("");
          markFailed.mutate({ orderId: order.id, failureReason }, { onError: err => setError(apiErrorMessage(err)) });
        }}>
          <p>{order.items?.length ? "با ثبت، فقط اقلام باقی‌مانده در انتظار تهیه لغو و مبلغ آن‌ها بازگردانده می‌شود؛ اقلام آماده یا ارسال‌شده حفظ می‌شوند. هزینه ارسال فقط وقتی هیچ قلمی آماده نشده باشد بازگردانده می‌شود." : "با ثبت، سفارش بسته می‌شود و کل مبلغ پرداخت‌شده، شامل هزینه ارسال پیش‌پرداخت‌شده، در صف بازگشت وجه قرار می‌گیرد."}</p>
          <Textarea label="علت تهیه‌نشدن سفارش" value={failureReason} onChange={event => setFailureReason(event.target.value)} required />
          <div className="admin-order-action-grid">
            <Button type="submit" variant="danger" disabled={markFailed.isPending || !failureReason.trim()}>ثبت عدم تهیه و درخواست بازگشت وجه</Button>
            <Button variant="ghost" disabled={markFailed.isPending} onClick={() => setShowFailure(false)}>انصراف</Button>
          </div>
        </form>}
      </section>}
      <OrderCancellation order={order} />
      {order.failure_reason && <p className="text-sm text-ink-600 mt-3">علت تهیه‌نشدن: {order.failure_reason}</p>}
      {error && <p role="alert" className="text-sm text-red-500 mt-3">{error}</p>}
    </Card>
  );
}

function OrderCancellation({ order }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [returned, setReturned] = useState(false);
  const preview = useMutation({ mutationFn: () => apiClient.get(`/orders/${order.id}/cancel/`).then(r => r.data) });
  const cancel = useMutation({
    mutationFn: () => apiClient.post(`/orders/${order.id}/cancel/`, { reason, return_confirmed: returned }),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  if (order.cancellation) return <section className="admin-order-actions"><h3>{order.cancellation.return_confirmed_at ? "مرجوعی تأیید شد و سفارش بسته شد" : "سفارش لغو شد"}</h3><p>{order.cancellation.reason}</p><p className="record-note">{formatJalaliShort(order.cancellation.created_at)} — مبالغ قابل بازگشت در بخش بازگشت وجه پیگیری می‌شوند.</p></section>;
  if (["cancelled", "refunded", "failed"].includes(order.status)) return null;
  return <section className="admin-order-actions order-cancellation" aria-label="لغو و مرجوعی سفارش">
    {!open ? <Button variant="ghost" onClick={() => { setOpen(true); preview.mutate(); }}>لغو یا مرجوعی سفارش</Button> : <>
      <h3>لغو یا مرجوعی کل سفارش</h3>
      {preview.isPending && <p role="status">در حال بررسی پرداخت‌ها و ارسال‌ها…</p>}
      {preview.isError && <p role="alert">{apiErrorMessage(preview.error)}</p>}
      {preview.data && <form onSubmit={event => { event.preventDefault(); cancel.mutate(); }} className="cancellation-form">
        <p>با ثبت، تهیه و ارسال باقی‌مانده اقلام این سفارش متوقف می‌شود. واریز به خریدار از بخش بازگشت وجه ثبت خواهد شد.</p>
        <dl className="record-facts"><div className="record-total"><dt>مبلغ پیشنهادی بازگشت</dt><dd>{formatToman(preview.data.refund_amount)}</dd></div></dl>
        <p className="record-note">مبالغی که قبلاً در صف بازگشت وجه هستند دوباره محاسبه نمی‌شوند. هزینه بسته مشترک یا ارسال‌شده باقی می‌ماند.</p>
        <Textarea label="دلیل لغو یا مرجوعی" value={reason} onChange={event => setReason(event.target.value)} required maxLength={2000} />
        {preview.data.requires_return && <label className="refund-confirm"><input type="checkbox" checked={returned} onChange={event => setReturned(event.target.checked)} />دریافت تمام اقلام ارسال‌شده این سفارش را تأیید می‌کنم.</label>}
        <div className="admin-order-action-grid"><Button type="submit" variant="danger" disabled={cancel.isPending || !reason.trim() || (preview.data.requires_return && !returned)}>{cancel.isPending ? "در حال ثبت…" : "تأیید لغو و ثبت بازگشت وجه"}</Button><Button variant="ghost" disabled={cancel.isPending} onClick={() => setOpen(false)}>انصراف</Button></div>
        {cancel.isError && <p role="alert">{apiErrorMessage(cancel.error)}</p>}
      </form>}
      {!preview.data && <Button variant="ghost" onClick={() => setOpen(false)}>بستن</Button>}
    </>}
  </section>;
}
