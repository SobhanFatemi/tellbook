import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ImageIcon } from "lucide-react";
import { useAdminRequests, useSendQuote, useMarkRequestFailed } from "../../../hooks/useAdminRequestsOrders";
import { EmptyState, StatusBadge, QueryBoundary } from "../../../components/Feedback";
import AdminActionPanel from "../../../components/AdminActionPanel";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import Tabs from "../../../components/Tabs";
import { Input, Textarea } from "../../../components/FormFields";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";
import { apiErrorMessage } from "../../../api/client";

const TABS = [
  { value: "", label: "همه" },
  { value: "pending", label: "در انتظار" },
  { value: "sourcing", label: "در حال تهیه" },
  { value: "ready", label: "آماده" },
  { value: "failed", label: "ناموفق" },
];

export default function AdminRequests() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = searchParams.get("status") || "";
  const { data: requests, isLoading, isError, refetch } = useAdminRequests(status);
  const [openAction, setOpenAction] = useState(null); // { requestId, type: "quote" | "fail" }

  return (
    <div>
      <h1 className="page-title">درخواست‌ها</h1>
      <Tabs tabs={TABS} active={status} onChange={(value) => setSearchParams(value ? { status: value } : {})} />

      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!requests?.length ? (
        <EmptyState title="درخواستی نیست" />
      ) : (
        <div className="flex flex-col gap-4">
          {requests.map((req) => (
            <RequestCard
              key={req.id}
              request={req}
              openAction={openAction}
              setOpenAction={setOpenAction}
            />
          ))}
        </div>
      )}
      </QueryBoundary>
    </div>
  );
}

function RequestCard({ request, openAction, setOpenAction }) {
  const sendQuote = useSendQuote();
  const markFailed = useMarkRequestFailed();
  const [form, setForm] = useState({ book_cost: "", service_fee: "0", shipping_fee: "0", estimated_days: "" });
  const [failureReason, setFailureReason] = useState("");
  const [error, setError] = useState("");

  const isOpenQuote = openAction?.requestId === request.id && openAction.type === "quote";
  const isOpenFail = openAction?.requestId === request.id && openAction.type === "fail";

  const submitQuote = (e) => {
    e.preventDefault();
    setError("");
    sendQuote.mutate(
      { requestId: request.id, payload: form },
      {
        onSuccess: () => setOpenAction(null),
        onError: (err) => setError(apiErrorMessage(err)),
      }
    );
  };

  const submitFail = (e) => {
    e.preventDefault();
    setError("");
    markFailed.mutate(
      { requestId: request.id, failureReason },
      {
        onSuccess: () => setOpenAction(null),
        onError: (err) => setError(apiErrorMessage(err)),
      }
    );
  };

  const canAct = ["pending", "sourcing"].includes(request.status);

  return (
    <Card className="admin-record">
      <div className="admin-record-heading">
        <div>
          <h3 className="font-semibold text-ink-700">{toPersianDigits(request.title || request.book?.title || "بدون عنوان")}</h3>
          <div className="admin-order-meta"><bdi>{toPersianDigits(request.buyer_phone)}</bdi><span>{formatJalaliShort(request.created_at)}</span></div>
        </div>
        <StatusBadge status={request.status} />
      </div>

      <div className="admin-record-grid"><section><h3>اطلاعات درخواست</h3>
      {!request.author && !request.description && !request.reference_image && <p className="record-note">توضیح یا تصویر دیگری ثبت نشده است.</p>}
      {request.author && <p className="text-sm text-ink-500">نویسنده: {request.author}</p>}
      {request.description && <p className="text-sm text-ink-500 mt-1">{request.description}</p>}
      {request.reference_image && (
        <a href={request.reference_image} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-dusty-500 mt-2">
          <ImageIcon size={14} /> دیدن عکس ارسالی
        </a>
      )}

      </section><section><h3>قیمت و پیگیری درخواست</h3>
      {!request.quote && <p className="record-note">قیمتی برای این درخواست ثبت نشده است.</p>}
      {request.quote && (
        <div className="request-quote-summary">
          <p>قیمت پیشنهادی: {formatToman(request.quote.total_price)}</p>
          <p className="text-ink-400">{toPersianDigits(request.quote.estimated_days)} روز — {request.status === "failed" ? "پیشنهاد غیرفعال — تهیه ناموفق" : request.quote.accepted_at ? "پذیرفته شده" : "منتظر پاسخ خریدار"}</p>
        </div>
      )}

      {request.status === "failed" && request.failure_reason && (
        <p className="mt-2 text-sm text-red-500">دلیل: {request.failure_reason}</p>
      )}

      </section></div>
      {canAct && <AdminActionPanel title="رسیدگی به درخواست">
        <div className="payment-review-actions request-review-actions">
          {!request.quote && <Button onClick={() => setOpenAction(isOpenQuote ? null : { requestId: request.id, type: "quote" })} aria-expanded={isOpenQuote}>ثبت قیمت</Button>}
          <Button variant="danger" onClick={() => setOpenAction(isOpenFail ? null : { requestId: request.id, type: "fail" })} aria-expanded={isOpenFail}>امکان تهیه نیست</Button>
        </div>
      {isOpenQuote && (
        <form onSubmit={submitQuote} className="review-action-form record-quote-form">
          <Input groupDigits label="قیمت کتاب (تومان)" type="number" value={form.book_cost} onChange={(e) => setForm({ ...form, book_cost: e.target.value })} required />
          <Input groupDigits label="هزینه خدمات" type="number" value={form.service_fee} onChange={(e) => setForm({ ...form, service_fee: e.target.value })} />
          <p className="text-sm text-ink-600">هزینه ارسال جداگانه هنگام ثبت بسته دریافت می‌شود.</p>
          <Input label="زمان تقریبی (روز)" type="number" value={form.estimated_days} onChange={(e) => setForm({ ...form, estimated_days: e.target.value })} required />
          {error && <p className="col-span-2 text-sm text-red-500">{error}</p>}
          <Button type="submit" className="col-span-2" disabled={sendQuote.isPending}>
            ارسال قیمت به خریدار
          </Button>
        </form>
      )}

      {isOpenFail && (
        <form onSubmit={submitFail} className="review-action-form flex flex-col gap-3">
          <Textarea label="دلیل عدم امکان تهیه" value={failureReason} onChange={(e) => setFailureReason(e.target.value)} required />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <Button type="submit" variant="danger" disabled={markFailed.isPending || !failureReason.trim()}>
            ثبت به عنوان ناموفق و بازگشت وجه (در صورت پرداخت)
          </Button>
        </form>
      )}
      </AdminActionPanel>}
    </Card>
  );
}
