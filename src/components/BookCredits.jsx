export default function BookCredits({ book, className = "" }) {
  const authors = [...new Set(book.authors || [])];
  const translators = [...new Set(book.translators || [])];
  if (!authors.length && !translators.length) return null;
  return <p className={className}>{authors.join("، ")}{translators.length > 0 && <><span>{authors.length ? " · " : ""}ترجمه: </span>{translators.join("، ")}</>}</p>;
}
