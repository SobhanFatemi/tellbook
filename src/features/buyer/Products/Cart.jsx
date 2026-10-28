import { useState } from "react";
import { groupOrderItems } from "../../../utils/orderItems";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { useCart } from "../../../hooks/useCart";
import { useAuth } from "../../../hooks/useAuth";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import Button, { ButtonLink } from "../../../components/Button";
import { Select } from "../../../components/FormFields";
import { emptyDelivery } from "../../../utils/delivery";
import PaymentPanel from "../../../components/PaymentPanel";
import BuyPanel from "../../../components/BuyPanel";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";

export default function Cart() {
  const cart = useCart();
  const auth = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const completedId = searchParams.get("order");
  const completed = useQuery({ queryKey: ["orders", "checkout", completedId], enabled: Boolean(completedId) && auth.isAuthenticated, queryFn: () => apiClient.get("/orders/mine/").then(r => r.data.find(o => String(o.id) === completedId)) });
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [deliveryChoice, setDeliveryChoice] = useState(emptyDelivery);
  const current = useQuery({ queryKey: ["cart-prices", cart.lines], enabled: cart.lines.length > 0, retry: false, queryFn: () => Promise.all(cart.lines.map(async line => {
    try {
      if (line.product_id) {
        const { data } = await apiClient.get(`/products/${line.product_id}/`);
        return { ...line, price: data.price, title: data.title, available: data.available, bookCount: data.components.reduce((n, c) => n + (c.book_id ? c.quantity : 0), 0) };
      }
      const { data } = await apiClient.get(`/catalog/${line.book_id}/`);
      const edition = data.editions.find(e => e.id === line.edition_id);
      return { ...line, price: edition?.price || line.price, available: Boolean(edition), bookCount: 1 };
    } catch (err) { if (err.response?.status === 404) return { ...line, available: false }; throw err; }
  })) });
  const buy = useMutation({ mutationFn: payload => apiClient.post('/products/checkout/', payload), onSuccess: response => { setSearchParams({ order: response.data.id }); cart.clear(); client.invalidateQueries(); }, onError: err => { setError(apiErrorMessage(err)); current.refetch(); client.invalidateQueries({ queryKey: ["store-settings"] }); } });
  const lines = current.data || [];
  const total = lines.reduce((sum, l) => sum + Number(l.price) * l.quantity, 0);
  if (completedId) return <div className="checkout-payment-page">
    <header className="checkout-page-heading"><div><h1 className="page-title">پرداخت سفارش</h1><p>خلاصه سفارش و ثبت رسید پرداخت</p></div><ButtonLink variant="ghost" to="/orders">پیگیری وضعیت سفارش</ButtonLink></header>
    <QueryBoundary isLoading={completed.isLoading} isError={completed.isError} onRetry={completed.refetch}>
      {completed.data ? <>
        <p className="checkout-confirmation">سفارش {toPersianDigits(completed.data.id)} ثبت شد. رسید را همین‌جا ارسال کنید.</p>
        <section className="checkout-invoice" aria-label="خلاصه سفارش">
          <h2>خلاصه سفارش <span>شماره {toPersianDigits(completed.data.id)}</span></h2>
          <ul className="checkout-invoice-items">{groupOrderItems(completed.data.items).map(item => <li key={item.key}><span>{toPersianDigits(item.title)} <bdi>×{toPersianDigits(item.quantity)}</bdi></span><strong>{formatToman(item.total)}</strong></li>)}</ul>
          <dl className="checkout-invoice-totals">
            <div><dt>جمع اقلام</dt><dd>{formatToman(completed.data.total_price)}</dd></div>
            <div><dt>هزینه ارسال</dt><dd>{completed.data.delivery?.mode === "shelf" ? "هنگام درخواست ارسال محاسبه می‌شود" : formatToman(completed.data.delivery?.shipping_fee || 0)}</dd></div>
          </dl>
        </section>
        <PaymentPanel payment={completed.data.payment} onUploaded={() => completed.refetch()} />

      </> : !completed.isLoading && <p>سفارش پیدا نشد. از بخش سفارش‌های من پیگیری کنید.</p>}
    </QueryBoundary>
  </div>;
  return <div className="cart-page"><h1 className="page-title">سبد خرید</h1>{!cart.lines.length ? <EmptyState title="سبد خریدت خالی است" description="پک یا محصولات دلخواهت را انتخاب کن؛ کتاب‌ها را هم می‌توانی از صفحه هر کتاب اضافه کنی." action={<ButtonLink to="/products">دیدن محصولات</ButtonLink>} /> : <QueryBoundary isLoading={current.isLoading} isError={current.isError} onRetry={current.refetch}><div className="cart-layout"><div>{lines.map((line, i) => <article className="cart-line" key={i}><div><Link to={line.product_id ? `/products/${line.product_id}` : `/books/${line.book_id}`} className="font-bold">{toPersianDigits(line.title)}</Link><p>{formatToman(line.price)}</p>{Number(line.price) !== Number(cart.lines[i]?.price) && <p role="status" className="text-sm text-maroon-700">قیمت به‌روز شده؛ مبلغ فعلی در جمع سبد محاسبه شده است.</p>}{!line.available && <p className="text-red-700">فعلاً قابل خرید نیست؛ از سبد حذف کنید.</p>}</div><div className="cart-line-actions"><Select label={`تعداد ${line.title}`} value={line.quantity} disabled={buy.isPending} onChange={e => cart.setQuantity(line, Number(e.target.value))}>{Array.from({ length: 20 }, (_, j) => <option key={j} value={j + 1}>{toPersianDigits(j + 1)}</option>)}</Select><Button variant="ghost" disabled={buy.isPending} onClick={() => cart.remove(line)}>حذف</Button></div></article>)}<ButtonLink className="mt-4" variant="ghost" to="/products">ادامه انتخاب محصولات</ButtonLink></div><aside className="cart-summary"><h2 className="section-title">جمع خرید</h2><p className="product-price">{formatToman(total)}</p><p className="text-sm text-ink-600">مبلغ همه اقلام با یک رسید پرداخت می‌شود. پس از تأیید پرداخت، اقلام آماده‌سازی می‌شوند. مهلت ۳۰روزه هر قلم از زمانی آغاز می‌شود که دایانا آن را آماده اعلام کند. هر پک یکجا ارسال می‌شود.</p>{!auth.isAuthenticated ? <ButtonLink to="/login" state={{ from: { pathname: '/cart' } }}>ورود و ادامه خرید</ButtonLink> : lines.length > 0 && lines.every(l => l.available) && <BuyPanel deliveryChoice={deliveryChoice} onDeliveryChange={setDeliveryChoice} key={`${total}-${cart.key}`} baseTotal={total} bookCount={lines.reduce((n, l) => n + (l.bookCount || 0) * l.quantity, 0)} allowDelivery isSubmitting={buy.isPending} confirmLabel="ثبت سفارش و پرداخت" onConfirm={(discount_code, delivery) => { setError(''); buy.mutate({ key: cart.key, discount_code, ...delivery, lines: lines.map(l => ({ ...(l.product_id ? { product_id: l.product_id } : { edition_id: l.edition_id }), quantity: l.quantity, expected_price: Number(l.price) })) }); }} />}{error && <p role="alert" className="text-red-700 mt-3">{error}</p>}</aside></div></QueryBoundary>}</div>;
}
