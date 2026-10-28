import { useState } from "react";
import { Plus, Trash2, Pencil } from "lucide-react";
import {
  useAdminDiscounts,
  useCreateDiscount,
  useUpdateDiscount,
  useDeleteDiscount,
} from "../../../hooks/useAdminDiscounts";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import { Input } from "../../../components/FormFields";
import JalaliDateField from "../../../components/JalaliDateField";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";
import { apiErrorMessage } from "../../../api/client";
import clsx from "clsx";

const emptyForm = {
  code: "",
  value: "",
  min_order_value: "0",
  usage_limit: "",
  per_user_limit: "1",
  valid_from: new Date().toISOString(),
  valid_until: "",
  is_active: true,
};

export default function AdminDiscounts() {
  const { data: codes, isLoading, isError, refetch } = useAdminDiscounts();
  const createDiscount = useCreateDiscount();
  const updateDiscount = useUpdateDiscount();
  const deleteDiscount = useDeleteDiscount();

  const [editingId, setEditingId] = useState(null); // id | "new" | null
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");

  const openNew = () => {
    setForm(emptyForm);
    setError("");
    setEditingId("new");
  };

  const openEdit = (code) => {
    setForm({
      ...code,
      usage_limit: code.usage_limit ?? "",
      valid_until: code.valid_until ?? "",
    });
    setError("");
    setEditingId(code.id);
  };

  const submit = (e) => {
    e.preventDefault();
    setError("");
    const payload = {
      code: form.code.trim(),
      value: form.value,
      min_order_value: form.min_order_value || 0,
      usage_limit: form.usage_limit === "" ? null : form.usage_limit,
      per_user_limit: form.per_user_limit || 1,
      valid_from: form.valid_from,
      valid_until: form.valid_until || null,
      is_active: form.is_active,
    };
    const options = {
      onSuccess: () => setEditingId(null),
      onError: (err) => setError(apiErrorMessage(err)),
    };
    if (editingId === "new") createDiscount.mutate(payload, options);
    else updateDiscount.mutate({ id: editingId, payload }, options);
  };

  const toggleActive = (code) =>
    updateDiscount.mutate({ id: code.id, payload: { is_active: !code.is_active } });

  const remove = (code) => {
    if (window.confirm(`کد «${code.code}» حذف بشه؟ (برای غیرفعال کردن موقت، از دکمه‌ی فعال/غیرفعال استفاده کن)`)) {
      deleteDiscount.mutate(code.id, { onError: (err) => setError(apiErrorMessage(err)) });
    }
  };

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="page-title">کدهای تخفیف</h1>
        <Button className="flex items-center gap-1.5 text-sm" onClick={openNew}>
          <Plus size={16} /> کد جدید
        </Button>
      </div>
      <p className="text-xs text-ink-400 mb-4">تخفیف‌ها فقط به‌صورت مبلغ ثابت (تومان) هستن و با کد دیگه‌ای قابل ترکیب نیستن.</p>

      {editingId && (
        <Card className="mb-5">
          <form onSubmit={submit} className="grid sm:grid-cols-2 gap-4">
            <Input label="کد" value={form.code} onChange={set("code")} required dir="ltr" />
            <Input groupDigits label="مبلغ تخفیف (تومان)" type="number" value={form.value} onChange={set("value")} required />
            <Input groupDigits label="حداقل مبلغ سفارش" type="number" value={form.min_order_value} onChange={set("min_order_value")} />
            <Input label="سقف کل استفاده (خالی = نامحدود)" type="number" value={form.usage_limit} onChange={set("usage_limit")} />
            <Input label="سقف استفاده‌ی هر کاربر" type="number" value={form.per_user_limit} onChange={set("per_user_limit")} required />
            <div />
            <JalaliDateField label="شروع اعتبار" value={form.valid_from} onChange={(v) => setForm({ ...form, valid_from: v })} />
            <JalaliDateField label="پایان اعتبار" optional value={form.valid_until} onChange={(v) => setForm({ ...form, valid_until: v })} />
            <label className="flex items-center gap-2 text-sm text-ink-600 sm:col-span-2">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              فعال
            </label>
            {error && <p className="text-sm text-red-500 sm:col-span-2">{error}</p>}
            <div className="sm:col-span-2 flex gap-2">
              <Button type="submit" disabled={createDiscount.isPending || updateDiscount.isPending}>
                ذخیره
              </Button>
              <Button type="button" variant="ghost" onClick={() => setEditingId(null)}>
                انصراف
              </Button>
            </div>
          </form>
        </Card>
      )}

      {error && !editingId && <p className="text-sm text-red-500 mb-3">{error}</p>}

      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
        {!codes?.length ? (
          <EmptyState title="هنوز کد تخفیفی نساختی" />
        ) : (
          <div className="flex flex-col gap-3">
            {codes.map((code) => (
              <Card key={code.id} className={clsx("flex items-center justify-between gap-3 flex-wrap", !code.is_active && "opacity-60")}>
                <div>
                  <p className="font-bold text-ink-700 tracking-wide" dir="ltr">{code.code}</p>
                  <p className="text-sm text-ink-500">
                    {formatToman(code.value)} تخفیف — حداقل سفارش {formatToman(code.min_order_value)}
                  </p>
                  <p className="text-xs text-ink-400">
                    از {formatJalaliShort(code.valid_from)}
                    {code.valid_until ? ` تا ${formatJalaliShort(code.valid_until)}` : " بدون تاریخ پایان"} — هر کاربر {toPersianDigits(code.per_user_limit)} بار
                    {code.usage_limit != null ? ` — سقف کل ${toPersianDigits(code.usage_limit)}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" className="text-sm" onClick={() => toggleActive(code)}>
                    {code.is_active ? "غیرفعال کن" : "فعال کن"}
                  </Button>
                  <Button variant="ghost" className="p-2" onClick={() => openEdit(code)} title="ویرایش">
                    <Pencil size={16} /> ویرایش
                  </Button>
                  <Button variant="ghost" className="p-2 text-red-500" onClick={() => remove(code)} title="حذف">
                    <Trash2 size={16} /> حذف
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}
