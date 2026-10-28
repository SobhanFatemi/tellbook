import { BundlePromotion } from "../Products/Products";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../../api/client";
import BookPostCard from "../../../components/BookPostCard";
import BookCredits from "../../../components/BookCredits";
import { Link } from "react-router-dom";
import { ArrowLeft, Search, BookPlus, Library } from "lucide-react";
import { useFeaturedBooks, useHomepageBooks } from "../../../hooks/useBooks";
import { QueryBoundary, EmptyState } from "../../../components/Feedback";
import { ButtonLink } from "../../../components/Button";
import BookCard from "../../../components/BookCard";
import { toPersianDigits } from "../../../utils/persianFormat";
import { useSyncExternalStore } from "react";

const phoneLayoutQuery = "(max-width: 600px)";
function subscribePhoneLayout(onChange) {
  const query = window.matchMedia(phoneLayoutQuery);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}
function getPhoneLayout() { return window.matchMedia(phoneLayoutQuery).matches; }
export default function Home() {
  const posts = useQuery({queryKey:["book-posts"],queryFn:()=>apiClient.get("/catalog/posts/").then(r=>r.data)});
  const featured = useFeaturedBooks();
  const catalog = useHomepageBooks();
  const phoneLayout = useSyncExternalStore(subscribePhoneLayout, getPhoneLayout, () => false);
  const IntroHeading = phoneLayout ? "h2" : "h1";
  const CatalogHeading = phoneLayout ? "h1" : "h2";
  const introduction = <section className="store-intro">
      <div className="intro-copy"><IntroHeading>جای کتاب بعدی‌ات<br />اینجا خالی است.</IntroHeading><p>در فهرست تلبوک بگرد. کتاب دلخواهت را سفارش بده، یا اگر پیدایش نکردی، از ما بخواه برایت تهیه‌اش کنیم.</p><div className="intro-actions"><ButtonLink to="/search"><Search size={19} />پیدا کردن کتاب</ButtonLink><ButtonLink to="/request-a-book" variant="ghost"><BookPlus size={19} />درخواست کتاب</ButtonLink></div></div>
      <div className="intro-catalog"><div className="intro-catalog-heading"><span>از میان کتاب‌های تلبوک</span><BookOpenMark /></div><QueryBoundary isLoading={catalog.isLoading} isError={catalog.isError} onRetry={catalog.refetch}>{catalog.data?.slice(0, 3).map(book => <Link className="intro-book" key={book.id} to={`/books/${book.id}`}><span><strong>{toPersianDigits(book.title)}</strong><BookCredits book={book} className="intro-book-credits" /></span><ArrowLeft size={20} /></Link>)}{!catalog.data?.length && <p className="text-sm py-5">کتاب دلخواهت را از بخش درخواست کتاب با ما در میان بگذار.</p>}</QueryBoundary></div>
    </section>;
  const bookCatalog = <section className="catalog-section"><div className="section-heading home-catalog-heading"><div>{phoneLayout && <span className="home-catalog-kicker"><Library size={17} strokeWidth={1.8} aria-hidden="true" />در فهرست تلبوک</span>}<CatalogHeading>{phoneLayout ? "کتاب‌ها منتظرن" : "در فهرست تلبوک"}</CatalogHeading><p>{phoneLayout ? "شاید کتاب بعدی‌ات همین‌جا باشه؛ ورق بزن یا از جستجوی بالا کمک بگیر." : "کتاب‌ها را ببین و نسخه مناسب خودت را انتخاب کن."}</p></div><ButtonLink to="/search" variant="ghost">{phoneLayout ? "دیدن همه کتاب‌ها" : "مرور فهرست"}<ArrowLeft size={17} /></ButtonLink></div><QueryBoundary isLoading={catalog.isLoading} isError={catalog.isError} onRetry={catalog.refetch}>{catalog.data?.length ? <div className="book-grid">{catalog.data.map(book => <BookCard key={book.id} book={book} />)}</div> : <EmptyState title="فهرست در حال آماده‌سازی است" description="می‌توانی همین حالا درخواست کتاب ثبت کنی." action={<ButtonLink to="/request-a-book">درخواست کتاب</ButtonLink>} />}</QueryBoundary></section>;
  return <div className="home-page">
    {!phoneLayout && <BundlePromotion />}
    {phoneLayout ? bookCatalog : introduction}
    {phoneLayout && <BundlePromotion />}
    {phoneLayout ? introduction : bookCatalog}
    {(posts.isLoading || posts.isError || posts.data?.length > 0) && <section className="catalog-section" aria-labelledby="book-introductions"><div className="section-heading"><div><h2 id="book-introductions">معرفی کتاب</h2><p>از میان کتاب‌ها، با عکس‌ها و نوشته‌های دایانا.</p></div></div><QueryBoundary isLoading={posts.isLoading} isError={posts.isError} onRetry={posts.refetch}><div className="book-posts">{posts.data?.map(post => <BookPostCard key={post.id} post={post} />)}</div></QueryBoundary></section>}
    {(featured.isLoading || featured.isError || featured.data?.length > 0) && <section className="catalog-section"><div className="section-heading"><h2>پیشنهاد تلبوک</h2></div><QueryBoundary isLoading={featured.isLoading} isError={featured.isError} onRetry={featured.refetch}><div className="book-grid">{featured.data?.map(item => <BookCard key={item.id} book={item.book} cover={item.cover_override} />)}</div></QueryBoundary></section>}
    <section className="shelf-explainer"><Library size={36} strokeWidth={1.5} /><div><h2>چند کتاب، یک ارسال؛ انتخاب با توست.</h2><p>کتاب‌های پرداخت‌شده و آماده تا ۳۰ روز روی قفسه‌ات می‌مانند. وقتی آماده بودی، کتاب‌های همان بسته را انتخاب کن و هزینه ارسال را بپرداز.</p></div><ButtonLink to="/shelf" variant="secondary">رفتن به قفسه من</ButtonLink></section>
  </div>;
}
function BookOpenMark() { return <Library size={22} strokeWidth={1.5} aria-hidden="true" />; }
