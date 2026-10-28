import { useState } from "react";
import { ChevronRight, ChevronLeft } from "lucide-react";
import Button, { ButtonLink } from "./Button";
import { formatNumber, toPersianDigits } from "../utils/persianFormat";
export default function BookPostCard({ post }) {
  const [index, setIndex] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const photos = post.images || [];
  const current = Math.min(index, Math.max(photos.length - 1, 0));
  return <article className="book-post">
    {photos.length > 0 && <div className="post-gallery"><img src={photos[current].image} alt={`${post.title}، تصویر ${toPersianDigits(current + 1)}`} loading="lazy" />{photos.length > 1 && <div className="post-gallery-controls"><Button variant="secondary" aria-label="تصویر قبلی" disabled={current === 0} onClick={() => setIndex(current - 1)}><ChevronRight size={18} /></Button><span aria-live="polite">{toPersianDigits(current + 1)} از {formatNumber(photos.length)}</span><Button variant="secondary" aria-label="تصویر بعدی" disabled={current === photos.length - 1} onClick={() => setIndex(current + 1)}><ChevronLeft size={18} /></Button></div>}</div>}
    <div className="post-copy"><h3>{toPersianDigits(post.title)}</h3><p className={expanded || post.body.length <= 240 ? "" : "post-excerpt"}>{toPersianDigits(post.body)}</p>{post.body.length > 240 && <Button variant="ghost" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? "بستن ادامه متن" : "خواندن ادامه معرفی"}</Button>}<div className="flex flex-wrap gap-2 mt-4">{post.books?.map(book => <ButtonLink key={book.id} variant="secondary" to={`/books/${book.id}`}>{toPersianDigits(book.title)}</ButtonLink>)}</div></div>
  </article>;
}
