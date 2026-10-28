import { useState } from "react";
import { Link } from "react-router-dom";
import { MapPin, Plus } from "lucide-react";
import { useMyAddresses, useAddAddress } from "../../../hooks/useFulfillment";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import { Input } from "../../../components/FormFields";
import { apiErrorMessage } from "../../../api/client";

const emptyForm = { full_name: "", phone: "", province: "", city: "", address_line: "", postal_code: "" };

export default function Addresses() {
  const { data: addresses, isLoading, isError, refetch } = useMyAddresses();
  const addAddress = useAddAddress();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState("");

  const submitAddress = (e) => {
    e.preventDefault();
    setError("");
    addAddress.mutate(form, {
      onSuccess: () => {
        setForm(emptyForm);
        setShowForm(false);
      },
      onError: (err) => setError(apiErrorMessage(err)),
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="page-title">آدرس‌های من</h1>
        <Button variant="ghost" className="flex items-center gap-1.5 text-sm" onClick={() => setShowForm((v) => !v)}>
          <Plus size={16} /> آدرس جدید
        </Button>
      </div>

      {showForm && (
        <Card>
          <form onSubmit={submitAddress} className="grid sm:grid-cols-2 gap-4">
            <Input label="نام گیرنده" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            <Input label="شماره تماس" type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} required dir="ltr" />
            <Input label="استان" value={form.province} onChange={(e) => setForm({ ...form, province: e.target.value })} required />
            <Input label="شهر" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required />
            <Input
              label="آدرس کامل"
              wrapperClassName="sm:col-span-2"
              value={form.address_line}
              onChange={(e) => setForm({ ...form, address_line: e.target.value })}
              required
            />
            <Input label="کد پستی" inputMode="numeric" value={form.postal_code} onChange={(e) => setForm({ ...form, postal_code: e.target.value })} dir="ltr" required pattern="[0-9]{10}" maxLength={10} />
            {error && <p className="text-sm text-red-500 sm:col-span-2">{error}</p>}
            <Button type="submit" className="sm:col-span-2" disabled={addAddress.isPending}>
              ذخیره آدرس
            </Button>
          </form>
        </Card>
      )}

      <Link to="/shelf" className="text-sm text-maroon-600 action-link py-2">انتخاب کتاب‌ها از قفسه و ثبت ارسال</Link>

      <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
      {!addresses?.length && !showForm ? (
        <EmptyState title="هنوز آدرسی ثبت نکردی" description="یک آدرس اضافه کن تا بتونی کتاب‌هات رو دریافت کنی." />
      ) : (
        addresses?.map((address) => (
          <Card key={address.id} className="flex items-start justify-between gap-4">
            <div className="flex gap-3">
              <MapPin className="text-dusty-500 shrink-0 mt-0.5" size={18} />
              <div>
                <p className="font-medium text-ink-700 text-sm">{address.full_name}</p>
                <p className="text-sm text-ink-400">
                  {address.province}، {address.city}، {address.address_line}
                </p>
              </div>
            </div>

          </Card>
        ))
      )}
      </QueryBoundary>
    </div>
  );
}
