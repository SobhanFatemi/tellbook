import { useState } from "react";
import { useStoreSettings, useSaveStoreSettings } from "../../../hooks/useStoreSettings";
import { QueryBoundary } from "../../../components/Feedback";
import { Input, Textarea } from "../../../components/FormFields";
import Button from "../../../components/Button";
import { apiErrorMessage } from "../../../api/client";
export default function StoreSettings() {
  const query = useStoreSettings();
  return <div className="settings-page"><h1 className="page-title">تنظیمات فروشگاه</h1><p className="text-sm text-ink-400 mb-8">هزینه ارسال و اطلاعات پرداخت را مدیریت کنید.</p><QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>{query.data && <SettingsForm initial={query.data} />}</QueryBoundary></div>;
}
function SettingsForm({ initial }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");
  const save = useSaveStoreSettings();
  const field = key => ({ value: form[key] ?? "", onChange: e => setForm({ ...form, [key]: e.target.value }) });
  const submit = event => {
    event.preventDefault(); setError("");
    const data = new FormData();
    for (const key of ["shipping_fee", "shipping_fee_over_six", "support_telegram", "transfer_recipient", "transfer_account", "transfer_instructions"]) data.append(key, form[key] ?? "");
    save.mutate(data, { onError: err => setError(apiErrorMessage(err)) });
  };
  return <form onSubmit={submit} className="space-y-5">
    <section className="settings-section"><div><h2>هزینه ارسال</h2><p>تعرفه با تعداد کتاب‌ها محاسبه می‌شود؛ کتاب‌های داخل پک هم شمرده می‌شوند. لوازم جانبی تعداد کتاب را زیاد نمی‌کنند.</p></div><div className="settings-fields"><Input groupDigits label="ارسال تا ۶ کتاب، شامل ۶ کتاب (تومان)" type="number" min="1" step="1" {...field("shipping_fee")} /><Input groupDigits label="ارسال ۷ کتاب و بیشتر (تومان)" type="number" min="1" step="1" {...field("shipping_fee_over_six")} /><p>بسته بدون کتاب هم با تعرفه کمتر ارسال می‌شود. تغییر مبلغ روی ارسال‌های ثبت‌شده اثر ندارد. خالی‌بودن این مقدار، ثبت ارسال جدید را غیرفعال می‌کند.</p></div></section>
    <section className="settings-section"><div><h2>پشتیبانی تلگرام</h2><p>خریدار برای هماهنگی پیک به این حساب پیام می‌دهد.</p></div><Input label="نام کاربری تلگرام دایانا" dir="ltr" placeholder="dayana_books" maxLength={33} {...field("support_telegram")} /></section>
    <section className="settings-section"><div><h2>اطلاعات واریز</h2><p>این اطلاعات هنگام پرداخت به خریدار نمایش داده می‌شود.</p></div><div className="settings-fields"><Input label="نام صاحب حساب" {...field("transfer_recipient")} /><Input label="شماره کارت یا حساب برای واریز" localizeDigits dir="ltr" {...field("transfer_account")} /><Textarea label="راهنمای واریز برای خریدار" {...field("transfer_instructions")} /></div></section>
    <div className="flex flex-wrap items-center justify-between gap-4 pt-3"><div>{save.isSuccess && <p role="status" className="text-sm text-green-800">تنظیمات ذخیره شد.</p>}{error && <p role="alert" className="text-red-700 text-sm">{error}</p>}</div><Button type="submit" disabled={save.isPending}>{save.isPending ? "در حال ذخیره…" : "ذخیره تنظیمات"}</Button></div>
  </form>;
}
