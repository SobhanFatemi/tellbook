import { useState } from "react";
import { Tag, Check, X } from "lucide-react";
import { Input } from "./FormFields";
import Button from "./Button";
import { Spinner } from "./Feedback";
import { validateDiscountCode } from "../hooks/useFulfillment";
import { formatToman } from "../utils/persianFormat";
import { apiErrorMessage } from "../api/client";

/**
 * onApplied(code, discountAmount) is called when a code checks out; pass
 * "" to onApplied when the buyer clears the code.
 */
export default function DiscountCodeField({ orderTotal, onApplied }) {
  const [code, setCode] = useState("");
  const [state, setState] = useState({ status: "idle" }); // idle | loading | valid | invalid

  const check = async () => {
    if (!code.trim()) return;
    setState({ status: "loading" });
    try {
      const result = await validateDiscountCode(code.trim(), orderTotal);
      setState({ status: "valid", discountAmount: result.discount_amount });
      onApplied(code.trim(), result.discount_amount);
    } catch (error) {
      setState({ status: "invalid", message: apiErrorMessage(error, "این کد تخفیف معتبر نیست") });
      onApplied("", 0);
    }
  };

  const clear = () => {
    setCode("");
    setState({ status: "idle" });
    onApplied("", 0);
  };

  return (
    <div>
      <div className="flex gap-2 items-end">
        <div className="flex-1">
          <Input
            label="کد تخفیف داری؟"
            placeholder="مثلاً WELCOME10"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            disabled={state.status === "valid"}
          />
        </div>
        {state.status === "valid" ? (
          <Button type="button" variant="ghost" onClick={clear}>
            <X size={16} /> حذف کد
          </Button>
        ) : (
          <Button type="button" variant="secondary" onClick={check} disabled={state.status === "loading" || !code.trim()}>
            {state.status === "loading" ? <Spinner className="w-4 h-4" /> : <><Tag size={16} /> اعمال کد</>}
          </Button>
        )}
      </div>
      {state.status === "valid" && (
        <p className="mt-1.5 text-sm text-green-600 flex items-center gap-1">
          <Check size={14} /> {formatToman(state.discountAmount)} تخفیف اعمال شد
        </p>
      )}
      {state.status === "invalid" && <p className="mt-1.5 text-sm text-red-500">{state.message}</p>}
    </div>
  );
}
