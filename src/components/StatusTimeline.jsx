import { Check, X } from "lucide-react";
import { toPersianDigits } from "../utils/persianFormat";
import clsx from "clsx";

const ORDER_STEPS = [
  { key: "awaiting_payment", label: "پرداخت" },
  { key: "paid", label: "تایید پرداخت" },
  { key: "sourcing", label: "تهیه کتاب" },
  { key: "stock_ready", label: "آماده ارسال" },
  { key: "shipped", label: "ارسال" },
];

const REQUEST_STEPS = [
  { key: "pending", label: "ثبت درخواست" },
  { key: "sourcing", label: "در حال تهیه" },
  { key: "ready", label: "آماده" },
];

/**
 * kind="order" | "request". Orders that skip SOURCING (instant in-stock
 * purchases) still render cleanly since we just compare index position.
 */
export default function StatusTimeline({ kind, status }) {
  const steps = kind === "order" ? ORDER_STEPS : REQUEST_STEPS;
  const isTerminalFailure = ["failed", "refunded", "cancelled"].includes(status);
  const currentIndex = steps.findIndex((s) => s.key === status);

  if (isTerminalFailure) {
    return (
      <div className="flex items-center gap-2 text-red-500 text-sm">
        <X size={16} />
        <span>{status === "refunded" ? "سفارش در فرایند بازگشت وجه قرار دارد" : status === "failed" ? "تهیه ناموفق" : "لغو شده"}</span>
      </div>
    );
  }

  return <ol className="order-timeline" aria-label="مراحل سفارش">{steps.map((step, index) => {
    const done = currentIndex > index;
    return <li key={step.key} className={clsx("timeline-step", done && "is-done", index === currentIndex && "is-current")} aria-current={index === currentIndex ? "step" : undefined}><span className="timeline-marker">{done ? <Check size={15} aria-hidden="true" /> : toPersianDigits(index + 1)}</span><span>{step.label}</span></li>;
  })}</ol>;
}
