import { Link } from "react-router-dom";
import { ChevronLeft, ClipboardList, Wallet, Truck, BookOpen, FileSpreadsheet, Tag } from "lucide-react";
import { useAdminDashboard } from "../../../hooks/useAdminDashboard";
import { QueryBoundary } from "../../../components/Feedback";
import { ButtonLink } from "../../../components/Button";
import { formatJalaliShort } from "../../../utils/jalali";
import { formatNumber, formatToman, toPersianDigits } from "../../../utils/persianFormat";

const QUEUES = [
  ["pending_payments", "بررسی رسیدهای پرداخت", Wallet, "#payment-review"],
  ["needs_quote", "قیمت‌گذاری درخواست‌ها", ClipboardList, "/admin/requests?status=pending"],
  ["shipments_to_send", "ارسال‌های آماده تحویل", Truck, "/admin/shipments"],
];
const STATUSES = {awaiting_payment: "در انتظار پرداخت", paid: "پرداخت شده", sourcing: "در حال تهیه", stock_ready: "آماده ارسال", shipped: "ارسال شده", refunded: "بازگشت وجه", failed: "تهیه ناموفق", cancelled: "لغو شده"};
export default function AdminDashboard() {
  const { data, isLoading, isError, refetch } = useAdminDashboard();
  return <div className="operations-dashboard">
    <header className="operations-heading"><div><h1>نمای کلی فروشگاه</h1><p>پرداخت‌ها، تهیه سفارش‌ها و ارسال‌ها را از اینجا پیگیری کنید.</p></div></header>
    <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>{data && <>
      <section className="operations-panel" aria-labelledby="daily-work"><header><h2 id="daily-work">نیازمند رسیدگی</h2><span>تعداد کارهای باز</span></header>
        <div className="operations-queues">{QUEUES.map(([key, label, Icon, to]) => <Link key={key} to={to} className="operations-queue"><Icon size={22} aria-hidden="true" /><span>{label}</span><strong>{formatNumber(data.counts[key])}</strong><ChevronLeft size={17} aria-hidden="true" /></Link>)}</div>
      </section>
      <section className="operations-panel" aria-labelledby="order-statuses"><header><h2 id="order-statuses">همه سفارش‌ها</h2><ButtonLink to="/admin/orders" variant="ghost">مشاهده سفارش‌ها</ButtonLink></header><div className="operations-statuses">{Object.entries(STATUSES).map(([status,label]) => <Link to={`/admin/orders?status=${status}`} key={status}><span>{label}</span><strong>{formatNumber(data.order_counts?.[status] ?? 0)}</strong><ChevronLeft size={15} aria-hidden="true" /></Link>)}</div></section>
      <div className="operations-columns">
        <WorkList id="payment-review" title="رسیدهای منتظر بررسی" count={data.counts.pending_payments} empty="رسیدی در انتظار بررسی نیست." items={data.pending_payments}>
          {item => <Link className="operations-record" to={item.order_id ? "/admin/orders?status=awaiting_payment" : "/admin/orders#shipping-payments"}><div><strong>{item.order_id ? `پرداخت سفارش ${formatNumber(item.order_id)}` : `پرداخت ارسال ${formatNumber(item.shipment_id)}`}</strong><span dir="ltr">{toPersianDigits(item.buyer_phone)}</span></div><div><strong>{formatToman(item.amount_expected)}</strong><span className="operations-action">بررسی رسید <ChevronLeft size={14} /></span></div></Link>}
        </WorkList>
        <WorkList title="درخواست‌های منتظر قیمت" count={data.counts.needs_quote} empty="درخواستی در انتظار قیمت‌گذاری نیست." items={data.needs_quote} to="/admin/requests?status=pending">
          {item => <Link className="operations-record" to="/admin/requests?status=pending"><div><strong>{toPersianDigits(item.title || "بدون عنوان")}</strong><span dir="ltr">{toPersianDigits(item.buyer_phone)}</span></div><div><span>{formatJalaliShort(item.created_at)}</span><span className="operations-action">بررسی درخواست <ChevronLeft size={14} /></span></div></Link>}
        </WorkList>
      </div>
      <section className="operations-panel" aria-labelledby="catalog-care"><header><h2 id="catalog-care">رسیدگی به فهرست کتاب‌ها</h2></header><div className="operations-catalog">{[["price_review","بازبینی قیمت‌ها",Tag,"/admin/prices"],["needs_review_books","بازبینی کتاب‌ها",BookOpen,"/admin/books/review"],["import_batches_active","فایل‌های اکسل در جریان",FileSpreadsheet,"/admin/imports"]].map(([key,label,Icon,to]) => <Link className="operations-queue" key={key} to={to}><Icon size={20} aria-hidden="true" /><span>{label}</span><strong>{formatNumber(data.counts[key] || 0)}</strong><ChevronLeft size={16} aria-hidden="true" /></Link>)}</div><p className="operations-footnote">آستانه بازبینی قیمت: {formatToman(data.price_review_threshold)}. پایین‌بودن قیمت به‌تنهایی به‌معنای اشتباه نیست.</p></section>
      <WorkList title="پایان مهلت نگهداری در قفسه" count={data.counts.expiring_soon} empty="در پنج روز آینده مهلت نگهداری هیچ قلمی تمام نمی‌شود." items={data.expiring_soon}>
        {item => <div className="operations-record"><div><strong>{toPersianDigits(item.book_title)}</strong><span dir="ltr">{toPersianDigits(item.buyer_phone)}</span></div><div><span>پایان مهلت</span><strong>{formatJalaliShort(item.expires_at)}</strong></div></div>}
      </WorkList>
    </>}</QueryBoundary>
  </div>;
}
function WorkList({id,title,count,empty,items,to,children}) {
  return <section id={id} className="operations-panel"><header><h2>{title}<span className="operations-count">{formatNumber(count || 0)}</span></h2>{to && <Link className="operations-action" to={to}>مشاهده همه <ChevronLeft size={15} /></Link>}</header>{items?.length ? <div className="operations-records">{items.map(item => <div key={item.id}>{children(item)}</div>)}</div> : <p className="operations-empty">{empty}</p>}{count > (items?.length || 0) && <p className="operations-footnote">نمایش {formatNumber(items.length)} مورد از {formatNumber(count)} مورد</p>}</section>;
}
