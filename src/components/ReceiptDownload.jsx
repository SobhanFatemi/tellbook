import { useState } from "react";
import { apiClient, apiErrorMessage } from "../api/client";
import Button from "./Button";

export default function ReceiptDownload({ paymentId }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const download = async () => {
    setPending(true);
    setError("");
    try {
      const { data } = await apiClient.get(`/payments/${paymentId}/receipt/`, { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const link = document.createElement("a");
      link.href = url;
      link.download = `receipt-${paymentId}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      setError(apiErrorMessage(err, "دریافت رسید انجام نشد. دوباره تلاش کنید."));
    } finally {
      setPending(false);
    }
  };
  return <div>
    <Button type="button" variant="ghost" onClick={download} disabled={pending}>
      {pending ? "در حال دریافت…" : "دریافت رسید پرداخت"}
    </Button>
    {error && <p role="alert" className="text-sm text-red-600 mt-2">{error}</p>}
  </div>;
}
