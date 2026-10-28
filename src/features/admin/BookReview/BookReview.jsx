import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { Input, Textarea } from "../../../components/FormFields";
import Button from "../../../components/Button";
import Card from "../../../components/Card";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import { toPersianDigits } from "../../../utils/persianFormat";
export default function BookReview() {
  const query = useQuery({ queryKey: ["admin", "book-review"], queryFn: () => apiClient.get("/publishers/needs-review/").then(r => r.data) });
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const books = query.data?.filter(book => [book.title, ...book.authors].join(" ").includes(search));
  return <div className="space-y-5"><h1 className="page-title">بازبینی کتاب‌ها</h1><p className="text-ink-500">این کتاب‌ها هنگام ورود فایل، مشابه کتاب دیگری تشخیص داده شده‌اند و تا تأیید شما در فهرست عمومی نمایش داده نمی‌شوند.</p>
    <Input label="جست‌وجو در صف بازبینی" value={search} onChange={e => setSearch(e.target.value)} />
    <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>
      {selected ? <ReviewEditor key={selected.id} book={selected} onClose={() => setSelected(null)} /> : books?.length ? <div className="review-list">{books.map(book => <div key={book.id} className="review-row"><div><h2>{toPersianDigits(book.title)}</h2><p>{book.authors.join("، ") || "نویسنده ثبت نشده"}</p></div><Button variant="secondary" onClick={() => setSelected(book)}>بررسی کتاب</Button></div>)}</div> : <EmptyState title={search ? "کتابی با این مشخصات پیدا نشد" : "صف بازبینی خالی است"} />}
    </QueryBoundary>
  </div>;
}
function ReviewEditor({ book, onClose }) {
  const client = useQueryClient();
  const [form, setForm] = useState({ ...book, authors: book.authors.join("، ") });
  const [error, setError] = useState("");
  const related = useQuery({ queryKey: ["review", "similar", book.title], queryFn: () => apiClient.get("/catalog/suggest/", { params: { q: book.title } }).then(r => r.data) });
  const save = useMutation({ mutationFn: approve => apiClient.patch(`/catalog/${book.id}/edit/`, { title: form.title, description: form.description, category: form.category, subcategory: form.subcategory, authors: form.authors.split(/[،,\n]/).map(s => s.trim()).filter(Boolean), needs_review: !approve }), onSuccess: () => { client.invalidateQueries({queryKey:["admin"]}); client.invalidateQueries({queryKey:["books"]}); onClose(); }, onError: e => setError(apiErrorMessage(e)) });
  const field = key => ({value: form[key] || "", onChange: e => setForm({...form, [key]:e.target.value})});
  return <Card><form className="space-y-4" onSubmit={e => {e.preventDefault(); setError(""); save.mutate(false);}}>
    <h2 className="section-title">بررسی {toPersianDigits(book.title)}</h2>
    <Input label="عنوان کتاب" required {...field("title")} /><Input label="نویسنده‌ها (با ویرگول جدا کنید)" {...field("authors")} />
    <div className="grid sm:grid-cols-2 gap-4"><Input label="دسته‌بندی" {...field("category")} /><Input label="زیرگروه" {...field("subcategory")} /></div><Textarea label="توضیحات کتاب" {...field("description")} />
    <section className="review-context"><h3>مقایسه با فهرست فروشگاه</h3><QueryBoundary isLoading={related.isLoading} isError={related.isError} onRetry={related.refetch}>{related.data?.length ? related.data.map(item => <a key={item.id} className="action-link" href={`/books/${item.id}`} target="_blank" rel="noreferrer">{toPersianDigits(item.title)} — {item.authors.join("، ")} (بازشدن در صفحه جدید)</a>) : <p>عنوان مشابهی در فهرست عمومی پیدا نشد. در صورت تردید، کتاب را در صف نگه دارید.</p>}</QueryBoundary></section>
    <p className="text-sm text-ink-500">تأیید، این رکورد را به‌عنوان کتاب مستقل منتشر می‌کند؛ رکوردها را با هم ادغام نمی‌کند. اگر کتاب تکراری است، فعلاً آن را در صف نگه دارید.</p>
    {error && <p role="alert" className="field-error">{error}</p>}
    <div className="flex flex-wrap gap-2"><Button type="submit" disabled={save.isPending}>ذخیره و نگه‌داشتن در صف</Button><Button variant="secondary" disabled={save.isPending || !form.title.trim()} onClick={() => {setError(""); save.mutate(true);}}>تأیید و نمایش در فروشگاه</Button><Button variant="ghost" onClick={onClose}>بازگشت به صف</Button></div>
  </form></Card>;
}
