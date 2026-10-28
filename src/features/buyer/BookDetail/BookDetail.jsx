import { addToCart } from "../../../hooks/useCart";
import BookCredits from "../../../components/BookCredits";
import { useParams, useNavigate } from "react-router-dom";
import { Camera } from "lucide-react";
import { useBookDetail } from "../../../hooks/useBooks";
import { QueryBoundary } from "../../../components/Feedback";
import { BookCover } from "../../../components/BookCard";
import Card from "../../../components/Card";
import Button, { ButtonLink } from "../../../components/Button";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";

export default function BookDetail() {
  const { id } = useParams();
  const { data: book, isLoading, isError, refetch } = useBookDetail(id);
  const navigate = useNavigate();

  return (
    <QueryBoundary isLoading={isLoading} isError={isError} onRetry={refetch}>
      {!book ? (
        <p className="text-center text-ink-400 py-16">این کتاب پیدا نشد.</p>
      ) : (
        <div className="book-detail">
          <BookCover src={book.cover} title={book.title} />

          <div>
            <h1 className="page-title">{toPersianDigits(book.title)}</h1>
            <BookCredits book={book} className="text-ink-400 mb-4" />

            {book.editions?.length > 0 && (
              <>
                <h2 className="text-sm font-bold text-ink-600 mb-2">نسخه‌های موجود از ناشرها</h2>
                <div className="flex flex-col gap-3">
                  {book.editions.map((edition) => (
                    <Card key={edition.id}>
                      <div className="flex flex-wrap items-center gap-3">
                        <BookCover src={edition.cover} title={book.title} className="edition-cover" />
                        <div className="flex-1">
                          <p className="font-medium text-ink-700 text-sm">{edition.publisher?.name}</p>
                          {edition.translator && <p className="text-xs text-ink-400">مترجم: {edition.translator}</p>}
                        </div>
                        <span className="font-bold text-ink-700">{formatToman(edition.price)}</span>
                      </div>
                      <p className="text-sm text-ink-500 mt-3">قابل تهیه از ناشر</p>
                      <Button variant="secondary" className="mt-3" onClick={() => { addToCart({ edition_id: edition.id, book_id: book.id, title: `${book.title} — ${edition.publisher?.name || ''}`, price: edition.price }); navigate('/cart'); }}>افزودن به سبد خرید</Button>
                      <details className="edition-specifications mt-3">
                        <summary>مشخصات این نسخه</summary>
                        <dl>
                          {[["شابک", edition.isbn], ["تعداد صفحات", edition.page_count], ["سال چاپ", edition.print_year], ["نوع جلد", edition.cover_type], ["تعداد جلد", edition.volume_count], ["نوبت چاپ", edition.print_run]].filter(([, value]) => value != null && value !== "").map(([label, value]) => <div key={label}><dt>{label}</dt><dd><bdi>{toPersianDigits(value)}</bdi></dd></div>)}
                        </dl>
                        {![edition.isbn, edition.page_count, edition.print_year, edition.cover_type, edition.volume_count, edition.print_run].some(Boolean) && <p className="text-sm text-ink-500">مشخصات بیشتری برای این نسخه ثبت نشده است.</p>}
                      </details>
                    </Card>
                  ))}
                </div>
              </>
            )}

            {!book.editions?.length && (
              <Card className="bg-cream-100 border-dashed">
                <p className="text-sm text-ink-500 mb-3">هنوز نسخه‌ای از این کتاب تو تلبوک ثبت نشده.</p>
                <ButtonLink to="/request-a-book" state={{ prefillTitle: book.title }} className="flex items-center gap-2 w-full justify-center">
                    <Camera size={16} /> درخواست این کتاب
                  </ButtonLink>
              </Card>
            )}

            {book.description && <section className="mt-8" aria-labelledby="book-introduction"><h2 id="book-introduction" className="section-title mb-3">معرفی کتاب</h2><p className="text-ink-500 leading-relaxed whitespace-pre-line">{book.description}</p></section>}

          </div>
        </div>
      )}
    </QueryBoundary>
  );
}
