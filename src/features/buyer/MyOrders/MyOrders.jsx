import { groupOrderItems } from "../../../utils/orderItems";
import { ShoppingBag } from "lucide-react";
import { useMyOrders } from "../../../hooks/useOrders";
import { EmptyState, StatusBadge, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import { ButtonLink } from "../../../components/Button";
import PaymentPanel from "../../../components/PaymentPanel";
import StatusTimeline from "../../../components/StatusTimeline";
import { formatNumber, formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";

export default function MyOrders() {
  const { data: orders, isLoading, isError, refetch } = useMyOrders();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="page-title">سفارش‌های من</h1>
      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!orders?.length ? (
          <EmptyState
            title="هنوز سفارشی نداری"
            description="کتاب‌های موجود رو بگرد و اولین سفارشت رو ثبت کن."
            action={
              <ButtonLink to="/" className="flex items-center gap-2">
                  <ShoppingBag size={16} /> رفتن به فروشگاه
                </ButtonLink>
            }
          />
        ) : (
          <>
            {orders.map((order) => (
              <Card key={order.id}>
                <div className="buyer-order-heading">
                  <div>
                    <h3 className="font-semibold text-ink-700">{toPersianDigits(groupOrderItems(order.items).map(i => i.title).join("، ") || order.quote?.book_title || (order.quote?.is_auto_quoted ? "خرید مستقیم" : "سفارش درخواستی"))}</h3>
                    <p className="text-xs text-ink-400">{formatJalaliShort(order.created_at)}</p>
                  </div>
                  <StatusBadge status={order.status} />
                </div>

                {order.items?.length > 0 && <ul className="text-sm text-ink-600 space-y-2 mb-3">{groupOrderItems(order.items).map((item, i) => <li key={i}>{toPersianDigits(item.title)} <bdi>×{formatNumber(item.quantity)}</bdi> — {formatToman(item.total)}{item.contents.length > 1 && <details><summary>محتویات خریداری‌شده</summary>{item.contents.map((c, j) => <p key={j}>{formatNumber(c.quantity)} × {toPersianDigits(c.title)}</p>)}</details>}</li>)}</ul>}
                <section className="buyer-order-progress"><div className="buyer-order-progress-heading"><h4>وضعیت تهیه و ارسال</h4>{order.payment?.shipment_id && <ButtonLink to="/shipments" variant="secondary">پیگیری وضعیت ارسال</ButtonLink>}</div><StatusTimeline kind="order" status={order.status} /></section>

                <div className="flex items-center justify-between mt-4 text-sm">
                  <span className="text-ink-500">مبلغ اقلام</span>
                  <span className="font-bold text-ink-700">{formatToman(order.total_price)}</span>
                </div>

                {order.cancellation && <p className="record-note">سفارش لغو شده است: {order.cancellation.reason}{order.cancellation.return_confirmed_at && " — دریافت مرجوعی تأیید شد."}</p>}
                {order.failure_reason && <p className="mt-3 text-sm text-ink-600">علت تهیه‌نشدن: {order.failure_reason}</p>}
                {order.payment?.shipment_id && <p className="mt-2 text-sm text-ink-600">جمع خرید و ارسال: {formatToman(order.payment.amount_expected)}</p>}
                {order.status === "awaiting_payment" && <PaymentPanel payment={order.payment} />}

              </Card>
            ))}
          </>
        )}
      </QueryBoundary>
    </div>
  );
}
