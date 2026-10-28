import { useState } from "react";
import { Camera } from "lucide-react";
import { useMyRequests } from "../../../hooks/useOrders";
import { useAcceptQuote } from "../../../hooks/useOrders";
import { QueryBoundary, EmptyState, StatusBadge } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button, { ButtonLink } from "../../../components/Button";
import BuyPanel from "../../../components/BuyPanel";
import StatusTimeline from "../../../components/StatusTimeline";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";
import { apiErrorMessage } from "../../../api/client";

export default function MyRequests() {
  const { data: requests, isLoading, isError, refetch } = useMyRequests();
  const acceptQuote = useAcceptQuote();
  const [openQuoteId, setOpenQuoteId] = useState(null);
  const [error, setError] = useState("");

  const handleAccept = (quoteId, discountCode) => {
    setError("");
    acceptQuote.mutate(
      { quoteId, discountCode },
      {
        onSuccess: () => setOpenQuoteId(null),
        onError: (err) => setError(apiErrorMessage(err)),
      }
    );
  };

  return (
    <div className="flex flex-col gap-4">
      <h1 className="page-title">درخواست‌های من</h1>
      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!requests?.length ? (
          <EmptyState
            title="هنوز درخواستی ثبت نکردی"
            description="کتابی که تو تلبوک پیدا نکردی رو باهامون در میون بذار."
            action={
              <ButtonLink to="/request-a-book" className="flex items-center gap-2">
                  <Camera size={16} /> درخواست کتاب
                </ButtonLink>
            }
          />
        ) : (
          <>
            {requests.map((req) => (
              <Card key={req.id}>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="font-semibold text-ink-700">{toPersianDigits(req.title || req.book?.title || "کتاب بدون عنوان")}</h3>
                    <p className="text-xs text-ink-400">{formatJalaliShort(req.created_at)}</p>
                  </div>
                  <StatusBadge status={req.status} />
                </div>

                {req.status === "failed" && req.failure_reason && (
                  <div className="mb-3 text-sm">
                    <p className="text-red-500">دلیل: {req.failure_reason}</p>
                    <p className="text-ink-400 text-xs mt-1">اگر پرداختی داشته‌اید، وضعیت پرداخت و بازگشت وجه را در «سفارش‌های من» بررسی کنید.</p>
                  </div>
                )}

                <StatusTimeline kind="request" status={req.status} />

                {req.status === "pending" && req.quote && !req.quote.accepted_at && (
                  <div className="mt-4 bg-cream-100 rounded-xl p-4">
                    <p className="text-sm font-medium text-ink-600 mb-1">قیمت پیشنهادی: {formatToman(req.quote.total_price)}</p>
                    <p className="text-xs text-ink-400 mb-3">زمان تقریبی تهیه: {toPersianDigits(req.quote.estimated_days)} روز</p>
                    {openQuoteId === req.quote.id ? (
                      <BuyPanel
                        baseTotal={req.quote.total_price}
                        isSubmitting={acceptQuote.isPending}
                        confirmLabel="تایید و پرداخت"
                        onConfirm={(code) => handleAccept(req.quote.id, code)}
                      />
                    ) : (
                      <Button className="w-full" onClick={() => setOpenQuoteId(req.quote.id)}>
                        بررسی قیمت و پرداخت
                      </Button>
                    )}
                  </div>
                )}
              </Card>
            ))}
            {error && <p className="text-sm text-red-500">{error}</p>}
          </>
        )}
      </QueryBoundary>
    </div>
  );
}
