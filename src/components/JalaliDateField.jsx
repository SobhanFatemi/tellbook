import { useId } from "react";
import DatePickerModule from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";

// The CommonJS bundle wraps its forwardRef component in a default export.
const DatePicker = DatePickerModule.default ?? DatePickerModule;

/**
 * Jalali (Shamsi) date picker. value / onChange use ISO strings, so callers
 * never touch the Persian calendar directly -- the backend stays Gregorian.
 */
export default function JalaliDateField({ label, value, onChange, optional = false }) {
  const id = useId();
  return (
    <div className="block">
      {label && <label htmlFor={id} className="block mb-1.5 text-sm font-medium text-ink-600">{label}</label>}
      <DatePicker
        id={id}
        value={value ? new Date(value) : null}
        onChange={(date) => onChange(date ? date.toDate().toISOString() : "")}
        calendar={persian}
        locale={persian_fa}
        format="YYYY/MM/DD"
        containerClassName="w-full"
        inputClass="field-control"
        placeholder={optional ? "بدون محدودیت" : "انتخاب تاریخ"}
        editable={false}
      />
    </div>
  );
}
