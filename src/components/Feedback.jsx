import { Loader2, AlertTriangle, Inbox } from "lucide-react";
import clsx from "clsx";
import Button from "./Button";

export function Spinner({ className }) {
  return <Loader2 className={clsx("animate-spin text-maroon-400", className)} />;
}

export function EmptyState({ title, description, action }) {
  return <div className="empty-state"><Inbox size={38} strokeWidth={1.4} aria-hidden="true" /><h3>{title}</h3>{description && <p>{description}</p>}{action}</div>;
}

/** Distinct from EmptyState -- a failed request isn't "nothing here", it's
 * "we couldn't check", and should always offer a retry. */
export function ErrorState({ onRetry, message = "در دریافت اطلاعات مشکلی پیش اومد." }) {
  return (
    <div className="flex flex-col items-center text-center py-12 px-4">
      <AlertTriangle className="text-red-400 mb-3" size={28} />
      <h3 className="text-base font-semibold text-ink-600 mb-1">مشکلی پیش اومد</h3>
      <p className="text-ink-400 text-sm max-w-xs mb-4">{message}</p>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          تلاش دوباره
        </Button>
      )}
    </div>
  );
}

/**
 * Wraps the loading/error/content branch every list page needs, so query
 * failures never silently render as "nothing here" again. Usage:
 *   <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
 *     ...content...
 *   </QueryBoundary>
 */
export function QueryBoundary({ isLoading, isError, onRetry, errorMessage, children }) {
  if (isLoading) {
    return (
      <div role="status" className="flex items-center justify-center gap-3 py-16 text-sm text-ink-400">
        <Spinner className="w-5 h-5" /> در حال دریافت اطلاعات…
      </div>
    );
  }
  if (isError) return <ErrorState onRetry={onRetry} message={errorMessage} />;
  return children;
}

const STATUS_STYLES = {
  // BookRequest
  pending: { label: "در انتظار بررسی", color: "bg-dusty-300/40 text-dusty-600" },
  sourcing: { label: "در حال تهیه", color: "bg-amber-200 text-amber-700" },
  ready: { label: "آماده", color: "bg-green-200 text-green-700" },
  failed: { label: "ناموفق", color: "bg-red-200 text-red-700" },
  // Order
  awaiting_payment: { label: "در انتظار پرداخت", color: "bg-dusty-300/40 text-dusty-600" },
  pending_verification: { label: "در حال بررسی پرداخت", color: "bg-amber-200 text-amber-700" },
  paid: { label: "پرداخت شده", color: "bg-green-100 text-green-700" },
  stock_ready: { label: "آماده ارسال", color: "bg-green-200 text-green-700" },
  shipped: { label: "ارسال شده", color: "bg-dusty-400/30 text-dusty-600" },
  waiting_books: { label: "منتظر آماده‌شدن کتاب", color: "bg-amber-100 text-amber-800" },
  preparing: { label: "در حال آماده‌سازی ارسال", color: "bg-dusty-300/40 text-dusty-600" },
  delivered: { label: "تحویل داده شده", color: "bg-green-300 text-green-800" },
  refunded: { label: "بازگشت وجه", color: "bg-ink-400/20 text-ink-500" },
  cancelled: { label: "لغو شده", color: "bg-ink-400/20 text-ink-500" },
  processed: { label: "پردازش شده", color: "bg-green-200 text-green-700" },
};

export function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || { label: status, color: "bg-cream-300 text-ink-500" };
  return (
    <span className={clsx("inline-flex shrink-0 px-3 py-1 rounded-md text-xs font-medium", style.color)}>
      {style.label}
    </span>
  );
}

export function Chip({ children, onClick, selected }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "px-3 py-1.5 rounded-full text-sm border transition-colors",
        selected
          ? "bg-maroon-500 text-cream-50 border-maroon-500"
          : "bg-white text-ink-600 border-cream-300 hover:border-maroon-400"
      )}
    >
      {children}
    </button>
  );
}
