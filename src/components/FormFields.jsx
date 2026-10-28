import { useId } from "react";
import clsx from "clsx";
import { toPersianDigits, toEnglishDigits, formatNumber, parseGroupedNumber } from "../utils/persianFormat";

export function Input({ label, error, className, wrapperClassName, type = "text", value, onChange, inputMode, pattern, localizeDigits = false, groupDigits = false, onFocus, onBlur, ...props }) {
  const id = useId();
  const normalize = groupDigits ? parseGroupedNumber : toEnglishDigits;
  const numeric = localizeDigits || type === "number" || type === "tel" || inputMode === "numeric" || inputMode === "decimal";
  const localizedPattern = pattern?.replaceAll("[0-9]", "[0-9۰-۹٠-٩]").replace(/^09/, "[0۰٠][9۹٩]");
  return <label className={clsx("field", wrapperClassName)} htmlFor={props.id || id}>
    {label && <span id={`${id}-label`} className="field-label">{label}</span>}
    <input {...props} id={props.id || id} aria-labelledby={label ? `${id}-label` : undefined} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined}
      className={clsx("field-control", className)} type={type === "number" ? "text" : type} inputMode={inputMode || (type === "number" ? "decimal" : type === "tel" ? "tel" : undefined)}
      pattern={localizedPattern || (groupDigits ? "[0-9۰-۹٠-٩.,٬\\s\\-]+" : undefined) || (type === "number" ? "[\\-]?[0-9۰-۹٠-٩]+([.٫][0-9۰-۹٠-٩]+)?" : undefined)}
      value={groupDigits && value !== "" && value != null ? formatNumber(value) : numeric && value != null ? toPersianDigits(value) : value}
      onFocus={onFocus}
      onBlur={onBlur}
      onInvalid={event => { if (!event.target.validity.customError) event.target.setCustomValidity(event.target.validity.valueMissing ? "این بخش را تکمیل کنید." : "مقدار واردشده معتبر نیست. آن را بررسی کنید."); }}
      onChange={event => {
        event.target.setCustomValidity("");
        if (type === "number") {
          const next = normalize(event.target.value);
          const number = Number(next);
          const invalid = next !== "" && (!Number.isFinite(number) || (props.min != null && number < Number(props.min)) || (props.max != null && number > Number(props.max)) || (props.step !== "any" && Math.abs((number - Number(props.min || 0)) / Number(props.step ?? 1) - Math.round((number - Number(props.min || 0)) / Number(props.step ?? 1))) > 1e-7));
          event.target.setCustomValidity(invalid ? "عدد واردشده در محدوده مجاز نیست." : "");
        }
        const input = event.target;
        const digitsBeforeCursor = groupDigits ? normalize(input.value.slice(0, input.selectionStart)).length : 0;
        onChange?.(numeric ? { ...event, target: { name: event.target.name, value: normalize(event.target.value) } } : event);
        if (groupDigits) requestAnimationFrame(() => {
          if (document.activeElement !== input) return;
          let cursor = 0, digits = 0;
          while (cursor < input.value.length && digits < digitsBeforeCursor) {
            if (/[0-9۰-۹٠-٩-]/.test(input.value[cursor])) digits++;
            cursor++;
          }
          input.setSelectionRange(cursor, cursor);
        });
      }} />
    {error && <span id={`${id}-error`} className="field-error">{error}</span>}
  </label>;
}
export function Textarea({ label, error, className, wrapperClassName, ...props }) {
  const id = useId();
  return <label className={clsx("field", wrapperClassName)} htmlFor={props.id || id}>{label && <span id={`${id}-label`} className="field-label">{label}</span>}<textarea {...props} id={props.id || id} className={clsx("field-control", className)} aria-labelledby={label ? `${id}-label` : undefined} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined} />{error && <span id={`${id}-error`} className="field-error">{error}</span>}</label>;
}
export function Select({ label, error, className, children, ...props }) {
  const id = useId();
  return <label className="field" htmlFor={props.id || id}>{label && <span id={`${id}-label`} className="field-label">{label}</span>}<select {...props} id={props.id || id} className={clsx("field-control", className)} aria-labelledby={label ? `${id}-label` : undefined} aria-invalid={error ? true : undefined} aria-describedby={error ? `${id}-error` : undefined}>{children}</select>{error && <span id={`${id}-error`} className="field-error">{error}</span>}</label>;
}
