import { useState } from "react";
import AdminActionPanel from "./AdminActionPanel";
import { useVerifyPayment } from "../hooks/useAdminPayments";
import { apiErrorMessage } from "../api/client";
import { formatToman } from "../utils/persianFormat";
import ReceiptDownload from "./ReceiptDownload";
import Button from "./Button";
import { Input } from "./FormFields";

export default function PaymentReview({ payment }) {
  const review = useVerifyPayment();
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState("");
  if (payment?.status !== "pending_verification") return null;
  const submit = approve => {
    setError("");
    review.mutate({ paymentId: payment.id, approve, reason }, { onError: err => setError(apiErrorMessage(err)) });
  };
  return <AdminActionPanel title="بررسی رسید پرداخت" summary={formatToman(payment.amount_expected)}>
    {rejecting && <Input label="دلیل رد رسید" value={reason} onChange={e => setReason(e.target.value)} />}
    <div className="payment-review-actions">
      <div className="payment-review-download"><ReceiptDownload paymentId={payment.id} /></div>
      <Button disabled={review.isPending} onClick={() => submit(true)}>تایید پرداخت</Button>
      <Button variant="danger" disabled={review.isPending || (rejecting && !reason.trim())} onClick={() => rejecting ? submit(false) : setRejecting(true)}>رد رسید</Button>
    </div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </AdminActionPanel>;
}
