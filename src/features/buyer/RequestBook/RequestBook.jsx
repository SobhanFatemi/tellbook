import { toPersianDigits } from "../../../utils/persianFormat";
import { useState } from "react";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { Check, X } from "lucide-react";
import Card from "../../../components/Card";
import Button from "../../../components/Button";
import { Input, Textarea } from "../../../components/FormFields";
import FileDropzone from "../../../components/FileDropzone";
import { Chip, Spinner } from "../../../components/Feedback";
import { useBookSuggestions } from "../../../hooks/useBooks";
import { useCreateRequest } from "../../../hooks/useOrders";
import { useDebouncedValue } from "../../../hooks/useDebouncedValue";
import { apiErrorMessage } from "../../../api/client";
import { useAuth } from "../../../hooks/useAuth";

export default function RequestBook() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [title, setTitle] = useState(location.state?.prefillTitle || "");
  const [author, setAuthor] = useState("");
  const [description, setDescription] = useState("");
  const [image, setImage] = useState(null);
  const [linkedBook, setLinkedBook] = useState(null); // {id, title} once a suggestion is picked
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const debouncedTitle = useDebouncedValue(title, 350);
  const { data: suggestions, isFetching: isSuggesting } = useBookSuggestions(linkedBook ? "" : debouncedTitle);
  const createRequest = useCreateRequest();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const canSubmit = Boolean(linkedBook || title.trim() || description.trim() || image);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    createRequest.mutate(
      {
        book: linkedBook?.id,
        title: linkedBook ? undefined : title.trim(),
        author: author.trim() || undefined,
        description: description.trim() || undefined,
        reference_image: image || undefined,
      },
      {
        onSuccess: () => setSubmitted(true),
        onError: (err) => setError(apiErrorMessage(err)),
      }
    );
  };

  if (submitted) {
    return (
      <Card className="max-w-lg mx-auto text-center py-10">
        <div className="w-14 h-14 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4">
          <Check size={26} />
        </div>
        <h1 className="page-title">درخواستت ثبت شد!</h1>
        <p className="text-sm text-ink-400 mb-5">به زودی بررسی می‌کنیم و قیمت و زمان تهیه رو برات می‌فرستیم.</p>
        <Button onClick={() => navigate("/requests")}>دیدن درخواست‌هام</Button>
      </Card>
    );
  }

  return (
    <Card className="max-w-lg mx-auto">
      <h1 className="page-title">درخواست کتاب</h1>
      <p className="text-sm text-ink-400 mb-5">اسمش رو می‌دونی، توضیح بده، یا فقط عکس جلدش رو بفرست — هر کدوم کافیه.</p>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          {linkedBook ? (
            <div className="flex items-center justify-between border border-green-300 bg-green-50 rounded-xl px-4 py-2.5">
              <span className="text-sm text-green-700 flex items-center gap-1.5">
                <Check size={14} /> لینک شده به «{toPersianDigits(linkedBook.title)}»
              </span>
              <button type="button" aria-label="حذف انتخاب کتاب" onClick={() => setLinkedBook(null)} className="text-green-700">
                <X size={14} />
              </button>
            </div>
          ) : (
            <>
              <Input label="اسم کتاب" placeholder="مثلاً: ملت عشق" value={title} onChange={(e) => setTitle(e.target.value)} />
              {isSuggesting && debouncedTitle.trim().length >= 2 && (
                <p className="text-xs text-ink-400 mt-1.5">در حال جستجو...</p>
              )}
              {!isSuggesting && suggestions?.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-ink-400 mb-1.5">منظورت یکی از این‌هاست؟</p>
                  <div className="flex flex-wrap gap-2">
                    {suggestions.map((s) => (
                      <Chip key={s.id} onClick={() => setLinkedBook({ id: s.id, title: s.title })}>
                        {toPersianDigits(s.title)}
                      </Chip>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <Input label="نویسنده (اختیاری)" value={author} onChange={(e) => setAuthor(e.target.value)} />
        <Textarea
          label="توضیحات (اختیاری)"
          placeholder="هر چیزی که یادته درباره‌ی کتاب — موضوعش، رنگ جلدش، هر چی..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <FileDropzone label="عکس جلد کتاب (اختیاری)" value={image} onChange={setImage} />

        {error && <p className="text-sm text-red-500">{error}</p>}

        <Button type="submit" disabled={!canSubmit || createRequest.isPending}>
          {createRequest.isPending ? <Spinner className="w-4 h-4 mx-auto" /> : "ثبت درخواست"}
        </Button>
      </form>
    </Card>
  );
}
