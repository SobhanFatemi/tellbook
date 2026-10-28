import BookCredits from "./BookCredits";
import { useState } from "react";
import { BookOpen, ArrowUpLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { formatToman, toPersianDigits } from "../utils/persianFormat";
export function BookCover({ src, title, className = "" }) {
  const [failed, setFailed] = useState(false);
  return <div className={`book-cover ${className}`}>{src && !failed ? <img src={src} alt={`جلد ${toPersianDigits(title)}`} loading="lazy" onError={() => setFailed(true)} /> : <div className="book-cover-fallback"><BookOpen size={30} strokeWidth={1.3} aria-hidden="true" /><span>تصویر جلد<br />ثبت نشده</span></div>}</div>;
}
export default function BookCard({ book, cover }) {
  return <Link to={`/books/${book.id}`} className="book-card">
    <BookCover src={cover || book.cover} title={book.title} />
    <div className="book-card-content"><h3>{toPersianDigits(book.title)}</h3><BookCredits book={book} className="book-card-author" />
      <div className="book-card-bottom"><span>{book.price_info?.price != null ? formatToman(book.price_info.price) : "مشاهده کتاب"}</span><ArrowUpLeft size={17} aria-hidden="true" /></div>
    </div>
  </Link>;
}
