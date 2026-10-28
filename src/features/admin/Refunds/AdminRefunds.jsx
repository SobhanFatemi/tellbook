import { useSearchParams } from "react-router-dom";
import { Check } from "lucide-react";
import { useState } from "react";
import { useAdminRefunds, useMarkRefundProcessed, useRefundPolicies, useSaveRefundPolicy } from "../../../hooks/useAdminRefunds";
import { Input } from "../../../components/FormFields";
import { apiErrorMessage } from "../../../api/client";
import { EmptyState, StatusBadge, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import Tabs from "../../../components/Tabs";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";

const TABS = [
  { value: "", label: "همه" },
  { value: "pending", label: "در انتظار" },
  { value: "processed", label: "پردازش شده" },
];

const REASON_LABELS = {
  sourcing_failed: "عدم امکان تهیه",
  expired: "انقضای مهلت تحویل",
  cancellation: "لغو سفارش",
  return: "مرجوعی پس از ارسال",
};

export default function AdminRefunds() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status") || "";
  const { data: refunds, isLoading, isError, refetch } = useAdminRefunds(status);

  return (
    <div>
      <h1 className="page-title">بازگشت وجه</h1>
      <ExpiredPolicyCard />
      <Tabs tabs={TABS} active={status} onChange={(value) => setSearchParams(value ? { status: value } : {})} />

      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!refunds?.length ? (
        <EmptyState title="بازگشت وجهی نیست" />
      ) : (
        <div className="flex flex-col gap-4">
          {refunds.map((refund) => (
            <Card key={refund.id} className="admin-record">
              <header className="admin-record-heading"><div><h2>سفارش {toPersianDigits(refund.order_id)}</h2><div className="admin-order-meta"><bdi>{toPersianDigits(refund.buyer_phone)}</bdi><span>{formatJalaliShort(refund.created_at)}</span></div></div><StatusBadge status={refund.status} /></header>
              <div className="admin-record-grid"><section><h3>علت بازگشت وجه</h3><p>{REASON_LABELS[refund.reason] || refund.reason}</p>{refund.status === "pending" && <p className="record-note">پس از واریز مبلغ به خریدار، انجام بازگشت وجه را ثبت کنید.</p>}</section><section><dl className="record-facts"><div><dt>مبلغ اولیه</dt><dd>{formatToman(refund.original_amount)}</dd></div><div><dt>مبلغ کسرشده</dt><dd>{formatToman(refund.deduction_amount)}</dd></div><div className="record-total"><dt>مبلغ قابل بازگشت</dt><dd>{formatToman(refund.refund_amount)}</dd></div></dl></section></div>
              {refund.status === "pending" ? <RefundProcessingForm refund={refund} /> : refund.processing_note && <footer className="admin-record-footer"><h3>یادداشت ثبت بازگشت وجه</h3><p>{refund.processing_note}</p></footer>}
            </Card>
          ))}
        </div>
      )}
      </QueryBoundary>

    </div>
  );
}

/** The only editable policy: what % of the book price is kept when a held
 * book expires. Sourcing failures are always refunded in full (backend rule). */
function ExpiredPolicyCard() {
  const { data: policies } = useRefundPolicies();
  const save = useSaveRefundPolicy();
  const existing = policies?.find((p) => p.reason === "expired");
  const [value, setValue] = useState(null); // null = untouched, show saved value
  const [message, setMessage] = useState("");

  const shown = value ?? (existing ? String(Number(existing.deduction_percentage)) : "0");

  const submit = (e) => {
    e.preventDefault();
    setMessage("");
    save.mutate(
      { existing, reason: "expired", deduction_percentage: shown },
      {
        onSuccess: () => {
          setValue(null);
          setMessage("ذخیره شد.");
        },
        onError: (err) => setMessage(apiErrorMessage(err)),
      }
    );
  };

  return (
    <Card className="refund-policy mb-5">
      <div>
      <h2 className="font-semibold text-ink-700 mb-1">کسر بابت انقضای مهلت نگهداری</h2>
      <p className="text-xs text-ink-400 mb-3">
        وقتی کتابی ۳۰ روز روی قفسه بمونه و ارسال نشه، این درصد از قیمت کتاب (بدون هزینه‌ی خدمات و ارسال) کسر و بقیه بازگردانده می‌شه.
        پیشنهاد اولیه برای عدم امکان تهیه، بازگشت کامل است؛ تغییر مبلغ نیاز به ثبت دلیل دارد.
      </p>
      </div><form onSubmit={submit} className="refund-policy-form">
        <div>
          <Input label="درصد کسر" type="number" min="0" max="100" step="0.01" value={shown} onChange={(e) => setValue(e.target.value)} />
        </div>
        <Button type="submit" disabled={save.isPending}>
          ذخیره
        </Button>
        {message && <span className="text-sm text-ink-500 pb-2.5">{message}</span>}
      </form>
    </Card>
  );
}

function RefundProcessingForm({ refund }) {
  const process = useMarkRefundProcessed();
  const [amount, setAmount] = useState(String(Number(refund.refund_amount)));
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const maximum = Number(refund.original_amount);
  const changed = Number(amount) !== Number(refund.refund_amount);
  const valid = amount !== "" && Number.isInteger(Number(amount)) && Number(amount) >= 0 && Number(amount) <= maximum;
  const submit = event => {
    event.preventDefault();
    setError("");
    process.mutate({ refundId: refund.id, refund_amount: amount, note }, { onError: err => setError(apiErrorMessage(err)) });
  };
  return <form className="admin-record-footer refund-processing-form" onSubmit={submit}>
    <div className="refund-amount-editor">
      <div><label htmlFor={`refund-range-${refund.id}`}>مبلغ بازگشت به خریدار</label>
        <input id={`refund-range-${refund.id}`} type="range" min="0" max={maximum} step="1" value={valid ? amount : 0} aria-valuetext={formatToman(valid ? amount : 0)} onChange={event => { setAmount(event.target.value); setConfirmed(false); }} />
        <div className="refund-range-labels"><span>{formatToman(0)}</span><span>{formatToman(maximum)}</span></div>
      </div>
      <Input label="مبلغ دقیق (تومان)" type="number" groupDigits min="0" max={maximum} step="1" value={amount} onChange={event => { setAmount(event.target.value); setConfirmed(false); }} />
    </div>
    <Input label={changed ? "دلیل تغییر مبلغ (الزامی)" : "یادداشت بازگشت وجه"} value={note} maxLength={2000} onChange={event => setNote(event.target.value)} required={changed} />
    <label className="refund-confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />{Number(amount) === 0 ? "تأیید می‌کنم این مورد بدون واریز بسته شود." : `تأیید می‌کنم ${formatToman(valid ? amount : 0)} به خریدار واریز کرده‌ام.`}</label>
    <div className="record-actions"><Button type="submit" disabled={!valid || !confirmed || (changed && !note.trim()) || process.isPending}><Check size={16} />{process.isPending ? "در حال ثبت…" : "ثبت نهایی بازگشت وجه"}</Button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
  </form>;
}
