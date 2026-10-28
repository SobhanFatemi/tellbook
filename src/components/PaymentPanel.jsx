import { CreditCard, Clock, ReceiptText } from "lucide-react";
import { formatJalali } from "../utils/jalali";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { paymentsApi } from "../api/payments";
import { useStoreSettings } from "../hooks/useStoreSettings";
import { apiErrorMessage } from "../api/client";
import { formatToman, toPersianDigits } from "../utils/persianFormat";
import FileDropzone from "./FileDropzone";
import Button from "./Button";

export default function PaymentPanel({ payment, onUploaded }) {
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const { data: store } = useStoreSettings();
  const client = useQueryClient();
  const upload = useMutation({ mutationFn: () => paymentsApi.uploadById(payment.id, file),
    onSuccess: () => { setFile(null); onUploaded?.(); client.invalidateQueries({ queryKey: ["orders"] }); client.invalidateQueries({ queryKey: ["shipments"] }); },
    onError: err => setError(apiErrorMessage(err)),
  });
  if (!payment || payment.status === "verified") return null;
  if (payment.status === "pending_verification") return <p role="status" className="mt-4 p-4 rounded-xl bg-amber-50 text-amber-800 text-sm">رسیدت رسید! پرداخت در حال بررسی است و مهلت پرداخت تا پایان بررسی متوقف می‌شود.</p>;
  return <section className="payment-panel" aria-label="واریز و ارسال رسید">
    <div className="payment-total">
      <span>مبلغ قابل واریز</span><strong>{formatToman(payment.amount_expected)}</strong>
      {payment.shipment_id && payment.order_id && <p>شامل اقلام سفارش و هزینه ارسال</p>}
    </div>
    <div className="payment-sections">
      <section className="payment-bank">
        <h2><CreditCard size={21} aria-hidden="true" />اطلاعات واریز</h2>
        {store?.transfer_account ? <>
          <dl className="payment-bank-details">
            <div><dt>به نام</dt><dd>{store.transfer_recipient || "نام صاحب حساب ثبت نشده است"}</dd></div>
            <div><dt>شماره کارت یا حساب</dt><dd className="payment-account" dir="ltr">{toPersianDigits(store.transfer_account)}</dd></div>
          </dl>
          {store.transfer_instructions && <p className="payment-instructions">{store.transfer_instructions}</p>}
        </> : <p className="payment-instructions">اطلاعات واریز هنوز ثبت نشده است. پیش از پرداخت با فروشگاه هماهنگ کنید.</p>}
        {payment.auto_cancel_at && <div className="payment-deadline"><Clock size={18} aria-hidden="true" /><div><span>مهلت ارسال رسید</span><time dateTime={payment.auto_cancel_at}>{formatJalali(payment.auto_cancel_at)}</time></div></div>}
      </section>
      <section className="payment-upload">
        <h2><ReceiptText size={21} aria-hidden="true" />ثبت رسید پرداخت</h2>
        {payment.status === "rejected" && <p role="alert" className="text-red-700 text-sm">رسید تایید نشد: {payment.rejection_reason} رسید اصلاح‌شده را بفرستید.</p>}
        <FileDropzone label="عکس رسید پرداخت" value={file} onChange={setFile} />
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <Button disabled={!file || upload.isPending} onClick={() => { setError(""); upload.mutate(); }}>{upload.isPending ? "در حال ارسال…" : "ارسال رسید"}</Button>
      </section>
    </div>
  </section>;
}
