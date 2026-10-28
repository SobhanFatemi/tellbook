import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { useCatalogMutation } from "../../../hooks/useCatalogAdmin";
import { Input, Select } from "../../../components/FormFields";
import Button, { ButtonLink } from "../../../components/Button";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import AdminPagination from "../../../components/AdminPagination";
import { formatNumber, formatToman, toPersianDigits } from "../../../utils/persianFormat";

export default function AdminPriceReview() {
  const [amount, setAmount] = useState(null);
  const [status, setStatus] = useState("active");
  const [page, setPage] = useState(1);
  const [confirmation, setConfirmation] = useState(null);
  const [notice, setNotice] = useState("");
  const prices = useQuery({
    queryKey: ["admin", "price-review", status, page],
    queryFn: () => apiClient.get("/publishers/price-review/", { params: { status, page } }).then(r => r.data),
  });
  const saveThreshold = useCatalogMutation(
    value => apiClient.patch("/publishers/price-review/", { threshold: value }).then(r => r.data),
    data => { setAmount(data.threshold); setPage(1); setConfirmation(null); setNotice(`حد بررسی فروشگاه روی ${formatToman(data.threshold)} ذخیره شد.`); },
  );
  const disable = useCatalogMutation(
    payload => apiClient.post("/publishers/price-review/", payload).then(r => r.data),
    data => { setNotice(`${formatNumber(data.disabled_count)} نسخه ناشر غیرفعال شد.`); setConfirmation(null); setPage(1); },
  );
  return <div className="space-y-6">
    <div><h1 className="page-title">بازبینی قیمت‌ها</h1><p>قیمت‌های کمتر از حد بررسی و مواردی که با فایل اصلی تطبیق ندارند؛ برای تصمیم‌گیری درباره قیمت و قابلیت سفارش.</p></div>
    <section className="surface space-y-4">
      <p>حد پیشنهادی اولیه <strong>۱۰۰٬۰۰۰ تومان</strong> است. این فقط نشانه‌ای برای بررسی است؛ کتاب کم‌حجم یا چاپ قدیمی ممکن است واقعاً ارزان باشد. تخفیف‌ها در این مقایسه دخالت ندارند.</p>
      <form className="flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); setNotice(""); saveThreshold.mutate(amount ?? prices.data?.threshold); }}>
        <Input groupDigits label="قیمت کمتر از (تومان)" type="number" min="1" max="999999999999" required value={amount ?? prices.data?.threshold ?? "100000"} onChange={e => setAmount(e.target.value)} />
        <Button variant="secondary" type="submit" disabled={saveThreshold.isPending || !prices.data}>ذخیره حد بررسی فروشگاه</Button>
      </form>
      {saveThreshold.isError && <p role="alert" className="field-error">{apiErrorMessage(saveThreshold.error)}</p>}
      <p className="text-sm text-ink-500">این حد برای کل فروشگاه ذخیره می‌شود و داشبورد هم از آن استفاده می‌کند.</p>
      <p className="text-sm text-ink-500">غیرفعال‌کردن، سفارش تازه از این نسخه ناشر را متوقف می‌کند؛ کتاب حذف نمی‌شود و سفارش‌ها و قفسه خریداران تغییر نمی‌کنند. فعال‌سازی دوباره از «ویرایش کتاب» ممکن است.</p>
    </section>
    {notice && <p role="status" className="text-green-800">{notice}</p>}
    <div className="section-heading">
      <Select label="وضعیت نسخه‌ها" value={status} onChange={e => { setStatus(e.target.value); setPage(1); setConfirmation(null); }}>
        <option value="active">قابل سفارش</option><option value="inactive">غیرفعال</option><option value="all">همه موارد</option>
      </Select>
      <Button disabled={!prices.data?.active_count || prices.isFetching || disable.isPending} onClick={() => { disable.reset(); setConfirmation({ threshold: prices.data.threshold, confirmation_token: prices.data.confirmation_token, count: prices.data.active_count }); }}>
        غیرفعال‌کردن همه {formatNumber(prices.data?.active_count || 0)} نسخه قابل سفارش
      </Button>
    </div>
    {confirmation && <section className="surface space-y-4" aria-labelledby="confirm-disable-prices">
      <h2 id="confirm-disable-prices" className="section-title">تأیید غیرفعال‌کردن گروهی</h2>
      <p>همه {formatNumber(confirmation.count)} نسخه قابل سفارش در این فهرست (قیمت کمتر از {formatToman(confirmation.threshold)} یا نیازمند تطبیق با فایل) در تمام صفحه‌ها غیرفعال شوند؟</p>
      <div className="flex flex-wrap gap-3"><Button disabled={disable.isPending} onClick={() => disable.mutate(confirmation)}>{disable.isPending ? "در حال ثبت…" : "تأیید؛ همه این نسخه‌ها غیرفعال شوند"}</Button><Button variant="ghost" disabled={disable.isPending} onClick={() => { setConfirmation(null); disable.reset(); }}>انصراف</Button></div>
      {disable.isError && <p role="alert" className="field-error">{apiErrorMessage(disable.error)} <Button variant="ghost" onClick={() => { setConfirmation(null); prices.refetch(); disable.reset(); }}>تازه‌سازی فهرست</Button></p>}
    </section>}
    <QueryBoundary isLoading={prices.isLoading} isError={prices.isError} onRetry={prices.refetch}>
      {prices.data?.results.length ? <div className="management-list">{prices.data.results.map(edition => <article key={edition.id} className="management-row">
        <div><h2>{toPersianDigits(edition.title)}</h2><p>{edition.publisher} · {edition.is_active ? "قابل سفارش" : "غیرفعال"}</p>{edition.review_note && <p className="text-sm text-amber-900 mt-2">{edition.review_note}</p>}<small>{edition.print_year ? `چاپ ${toPersianDigits(edition.print_year)} · ` : ""}{edition.page_count ? `${formatNumber(edition.page_count)} صفحه` : "تعداد صفحات ثبت نشده"}</small></div>
        <div className="management-row-actions"><strong>{formatToman(edition.price)}</strong><ButtonLink variant="secondary" to={`/admin/books/${edition.book}`}>ویرایش کتاب و قیمت</ButtonLink></div>
      </article>)}</div> : <EmptyState title="قیمتی در این محدوده پیدا نشد" description="حد قیمت یا وضعیت نسخه‌ها را تغییر دهید." />}
      <AdminPagination data={prices.data} page={page} onChange={setPage} />
    </QueryBoundary>
  </div>;
}
