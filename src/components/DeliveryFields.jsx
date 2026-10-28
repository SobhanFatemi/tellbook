import { useId } from "react";
import { Input, Select } from "./FormFields";
import Button from "./Button";
import { useMyAddresses } from "../hooks/useFulfillment";
import { useAuth } from "../hooks/useAuth";
import { formatToman, toPersianDigits } from "../utils/persianFormat";

export default function DeliveryFields({ value, onChange, store, bookCount, allowShelf = true, disabled = false }) {
  const name = useId();
  const { user, isAuthenticated } = useAuth();
  const addresses = useMyAddresses(isAuthenticated);
  const set = (key, next) => onChange({ ...value, [key]: next });
  const postalFee = Number(bookCount <= 6 ? store?.shipping_fee : store?.shipping_fee_over_six);
  return <fieldset className="delivery-fields space-y-4" disabled={disabled}>
    <legend className="font-bold mb-3">روش دریافت</legend>
    <label className="flex items-start gap-3 py-2"><input type="radio" className="mt-1" name={name} checked={value.mode === "ship_when_ready"} onChange={() => set("mode", "ship_when_ready")} /><span>ارسال پس از آماده‌شدن<small className="block mt-1 text-ink-600">{toPersianDigits(bookCount)} کتاب؛ {bookCount <= 6 ? "تعرفه تا ۶ کتاب" : "تعرفه ۷ کتاب و بیشتر"} — {postalFee > 0 ? formatToman(postalFee) : "تعرفه هنوز ثبت نشده"}</small></span></label>
    <label className="flex items-start gap-3 py-2"><input type="radio" className="mt-1" name={name} checked={value.mode === "courier"} onChange={() => set("mode", "courier")} /><span>خودم پیک می‌گیرم<small className="block mt-1 text-ink-600">هزینه ارسال به تلبوک: ۰ تومان؛ هماهنگی و هزینه پیک با شماست.</small></span></label>
    {allowShelf && <label className="flex items-start gap-3 py-2"><input type="radio" className="mt-1" name={name} checked={value.mode === "shelf"} onChange={() => set("mode", "shelf")} /><span>روی قفسه نگه دارید<small className="block mt-1 text-ink-600">هزینه ارسال هنگام درخواست ارسال محاسبه می‌شود.</small></span></label>}
    {value.mode === "courier" && <div className="space-y-3"><p className="text-sm">تحویل فقط با نام خودتان انجام می‌شود. پس از آماده‌شدن سفارش، گرفتن پیک را با پشتیبانی هماهنگ کنید.</p>{user?.full_name ? <p className="font-semibold">نام تحویل‌گیرنده: {user.full_name}</p> : <Input label="نام و نام خانوادگی خودتان" value={value.collector_name} maxLength={200} onChange={e => set("collector_name", e.target.value)} required />}{store?.support_telegram && <a className="action-link inline-block py-2" href={`https://t.me/${store.support_telegram}`} target="_blank" rel="noreferrer">پشتیبانی در تلگرام</a>}</div>}
    {value.mode === "ship_when_ready" && <div className="space-y-4">
      {addresses.isLoading && <p role="status">در حال دریافت آدرس‌ها…</p>}
      {addresses.isError && <p role="alert">دریافت آدرس‌های قبلی انجام نشد. می‌توانید آدرس را همین‌جا وارد کنید. <Button variant="ghost" onClick={() => addresses.refetch()}>تلاش دوباره</Button></p>}
      {!!addresses.data?.length && <Select label="آدرس ارسال" value={value.addressId || "new"} onChange={e => set("addressId", e.target.value)}><option value="new">واردکردن آدرس جدید</option>{addresses.data.map(a => <option key={a.id} value={a.id}>{a.full_name}، {a.city}، {a.address_line}</option>)}</Select>}
      {(!value.addressId || value.addressId === "new") && <div className="grid sm:grid-cols-2 gap-4">{[["full_name", "نام گیرنده", 200], ["phone", "شماره تماس", 11], ["province", "استان", 100], ["city", "شهر", 100], ["address_line", "آدرس کامل", 500], ["postal_code", "کد پستی", 10]].map(([key, label, max]) => <Input key={key} label={label} value={value.address[key]} maxLength={max} localizeDigits={key === "phone" || key === "postal_code"} inputMode={key === "phone" || key === "postal_code" ? "numeric" : undefined} wrapperClassName={key === "address_line" ? "sm:col-span-2" : undefined} onChange={e => set("address", { ...value.address, [key]: e.target.value })} required />)}</div>}
      <p className="text-sm text-ink-600">بسته‌های آماده حداقل هفته‌ای یک‌بار و حداکثر تا پنجشنبه ارسال می‌شوند. زمان تهیه کتاب جدا از زمان ارسال است.</p>
    </div>}
  </fieldset>;
}
