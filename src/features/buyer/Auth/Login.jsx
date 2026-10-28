import { toPersianDigits } from "../../../utils/persianFormat";
import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import { Input } from "../../../components/FormFields";
import Logo from "../../../components/Logo";
import { authApi } from "../../../api/auth";
import { apiErrorMessage } from "../../../api/client";
import { useAuth } from "../../../hooks/useAuth";

export default function Login() {
  const [step, setStep] = useState("phone"); // phone | code
  const [phone, setPhone] = useState("");
  const [developmentCode, setDevelopmentCode] = useState("");
  const [challengeId, setChallengeId] = useState(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const requestCode = async (e) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const { data } = await authApi.requestOtp(phone);
      setChallengeId(data.challenge_id);
      setDevelopmentCode(data.channel === "development" ? data.development_code : "");
      setCode("");
      setStep("code");
    } catch (err) {
      setError(apiErrorMessage(err, "شماره موبایل معتبر نیست"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const verifyCode = async (e) => {
    e.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const user = await authApi.verifyOtp(phone, code, challengeId);
      login(user);
      const fallback = user.role === "creator" ? "/admin" : "/";
      navigate((location.state?.from ? `${location.state.from.pathname}${location.state.from.search || ""}` : fallback), { replace: true });
    } catch (err) {
      setError(apiErrorMessage(err, "کد وارد شده اشتباهه"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-md mx-auto py-3">
      <div className="flex justify-center mb-6">
        <Logo size="lg" />
      </div>
      <Card>
        {step === "phone" ? (
          <form onSubmit={requestCode} className="flex flex-col gap-4">
            <h1 className="page-title">ورود به تلبوک</h1>
            <Input
              label="شماره موبایل"
              type="tel"
              placeholder="۰۹۱۲۱۲۳۴۵۶۷"
              autoComplete="tel-national"
              inputMode="numeric"
              pattern="09[0-9]{9}"
              maxLength={11}
              value={phone}
              onChange={(e) => setPhone(normalizeDigits(e.target.value))}
              required
              dir="ltr"
              className="text-left"
            />
            {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
            <p className="text-sm text-ink-600">برای ورود یا ساخت حساب، شماره موبایلت را وارد کن.</p>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "در حال ارسال..." : "دریافت کد تایید"}
            </Button>
          </form>
        ) : (
          <form onSubmit={verifyCode} className="flex flex-col gap-4">
            <h1 className="page-title">کد تایید رو وارد کن</h1>
            <p className="text-sm text-ink-600 text-center">ورود با شماره <bdi>{toPersianDigits(phone)}</bdi></p>
            {developmentCode && <div role="status" className="rounded-xl border border-yellow-400 bg-yellow-50 p-4 text-yellow-950">
              <p className="font-semibold text-sm">حالت توسعه — ورود آزمایشی</p>
              <p className="text-sm mt-2 leading-relaxed">پیامکی ارسال نشده است. این کد فقط برای تست نمایش داده می‌شود و تا ۵ دقیقه معتبر است.</p>
              <output aria-label="کد ورود آزمایشی" className="block mt-3 text-center text-2xl font-bold tabular-nums select-all" dir="ltr">{toPersianDigits(developmentCode)}</output>
            </div>}
            <Input
              label="کد تایید"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              autoFocus
              value={code}
              onChange={(e) => setCode(normalizeDigits(e.target.value))}
              required
              dir="ltr"
              className="text-center tracking-widest text-lg"
            />
            {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "در حال بررسی..." : "ورود"}
            </Button>
            <button type="button" onClick={() => { setStep("phone"); setDevelopmentCode(""); setCode(""); setError(""); }} className="action-link">
              تغییر اطلاعات یا دریافت کد جدید
            </button>
          </form>
        )}
      </Card>
    </div>
  );
}

function normalizeDigits(value) {
  return value.replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String("٠١٢٣٤٥٦٧٨٩".indexOf(digit)));
}
