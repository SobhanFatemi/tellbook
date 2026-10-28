const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
export function toPersianDigits(value) {
  return String(value ?? "").replace(/[0-9]/g, digit => PERSIAN_DIGITS[digit]);
}
export function toEnglishDigits(value) {
  return String(value ?? "").replace(/[۰-۹]/g, digit => String(PERSIAN_DIGITS.indexOf(digit))).replace(/[٠-٩]/g, digit => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit))).replace(/٫/g, ".");
}
export function formatNumber(value) {
  if (value == null || value === "") return "";
  const number = Number(value);
  if (!Number.isFinite(number)) return toPersianDigits(value);
  return new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 3 }).format(number).replaceAll("٬", ".");
}
export function parseGroupedNumber(value) {
  return toEnglishDigits(value).replace(/[.,٬\s]/g, "");
}
export function formatToman(amount) {
  return `${formatNumber(Number(amount) || 0)} تومان`;
}
