import { toPersianDigits } from "./persianFormat.js";

const messages = [
  [/Invalid or expired code/i, "کد ورود نادرست است یا مهلت آن تمام شده. کد جدید دریافت کنید."],
  [/valid Iranian mobile/i, "شماره موبایل را به‌صورت ۰۹ و ۹ رقم بعد از آن وارد کنید."],
  [/Phone sign-in is unavailable|SMS delivery is not configured/i, "ورود تلفنی در حال حاضر فعال نیست. لطفاً با فروشگاه هماهنگ کنید."],
  [/Account sign-in is unavailable/i, "ورود به این حساب غیرفعال است. با فروشگاه تماس بگیرید."],
  [/Request was throttled/i, "تعداد تلاش‌ها زیاد شده است. کمی صبر کنید و دوباره تلاش کنید."],
  [/Authentication credentials|token.*(invalid|expired)|not authenticated/i, "برای ادامه، دوباره وارد حساب خود شوید."],
  [/permission|not allowed/i, "حساب شما اجازه انجام این کار را ندارد."],
  [/shipping fee changed/i, "هزینه ارسال تغییر کرده است. مبلغ جدید را بررسی و دوباره تایید کنید."],
  [/Shipping is unavailable until/i, "فروشگاه هنوز هزینه ارسال را تنظیم نکرده است."],
  [/Some selected books are unavailable/i, "وضعیت بعضی کتاب‌های انتخابی تغییر کرده است. قفسه را تازه‌سازی و انتخاب‌ها را بررسی کنید."],
  [/No priced copies available|No longer available from this publisher/i, "این نسخه دیگر قابل سفارش نیست. نسخه دیگری را انتخاب کنید."],
  [/Receipt image must be no larger|file.*too large/i, "حجم تصویر نباید بیشتر از ۵ مگابایت باشد."],
  [/Upload a valid image|valid image/i, "یک تصویر معتبر با فرمت JPG، PNG یا WebP انتخاب کنید."],
  [/No file was submitted|submitted data was not a file/i, "ابتدا تصویر رسید را انتخاب کنید."],
  [/required|may not be blank|may not be null/i, "این بخش را تکمیل کنید."],
  [/valid integer|valid number|valid decimal|valid string|valid value/i, "مقدار واردشده معتبر نیست. آن را بررسی کنید."],
  [/Ensure this value is greater than or equal to (.+)\./i, m => `مقدار باید حداقل ${m[1]} باشد.`],
  [/Ensure this value is less than or equal to (.+)\./i, m => `مقدار باید حداکثر ${m[1]} باشد.`],
  [/Ensure this field has no more than (\d+) characters/i, m => `حداکثر ${m[1]} نویسه وارد کنید.`],
  [/discount.*expired|code.*expired/i, "مهلت استفاده از این کد تخفیف تمام شده است."],
  [/discount.*(invalid|not found)|code.*(invalid|not found|inactive)/i, "کد تخفیف معتبر یا فعال نیست."],
  [/usage limit|already used|limit.*reached/i, "سقف استفاده از این کد تخفیف تکمیل شده است."],
  [/minimum.*order|minimum.*amount/i, "مبلغ سفارش به حداقل لازم برای این کد تخفیف نرسیده است."],
  [/already|no longer|Only a|Only paid|cannot|must have|requires verified|Review the submitted/i, "وضعیت این مورد اجازه انجام این کار را نمی‌دهد. اطلاعات صفحه را تازه‌سازی و دوباره بررسی کنید."],
  [/not found|does not exist|Invalid pk/i, "مورد درخواستی پیدا نشد. صفحه را تازه‌سازی کنید."],
];
const fields = { phone: "شماره موبایل", postal_code: "کد پستی", proof_image: "تصویر رسید", shipping_fee: "هزینه ارسال", expected_shipping_fee: "هزینه ارسال", code: "کد", tracking_code: "کد رهگیری", failure_reason: "علت تهیه‌نشدن", full_name: "نام", book_cost: "قیمت کتاب", unit_price: "قیمت", value: "مبلغ", title: "عنوان", address_id: "آدرس", estimated_days: "زمان تقریبی" };
export function translateApiMessage(value, fallback = "انجام این کار ممکن نشد. اطلاعات را بررسی و دوباره تلاش کنید.") {
  if (typeof value !== "string") return fallback;
  if (/[\u0600-\u06ff]/.test(value)) return toPersianDigits(value);
  for (const [pattern, translation] of messages) {
    const match = value.match(pattern);
    if (match) return toPersianDigits(typeof translation === "function" ? translation(match) : translation);
  }
  return fallback;
}
export function localizedApiError(error, fallback) {
  if (!error?.response) return error?.code === "ECONNABORTED" ? "پاسخ فروشگاه دیر رسید. اتصال اینترنت را بررسی و دوباره تلاش کنید." : "اتصال به فروشگاه برقرار نشد. اتصال اینترنت را بررسی و دوباره تلاش کنید.";
  const data = error.response.data;
  if (error.response.status >= 500) return fallback || "فروشگاه موقتاً پاسخ نمی‌دهد. کمی بعد دوباره تلاش کنید.";
  if (!data || typeof data !== "object") return fallback || "دریافت پاسخ انجام نشد. دوباره تلاش کنید.";
  const key = data.detail ? "detail" : Object.keys(data)[0];
  let value = data[key];
  while (Array.isArray(value)) value = value[0];
  const message = translateApiMessage(value, fallback);
  return fields[key] ? `${fields[key]}: ${message}` : message;
}
