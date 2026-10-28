import { useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Package, ArrowLeft } from "lucide-react";
import { apiClient } from "../../../api/client";
import { QueryBoundary, EmptyState } from "../../../components/Feedback";
import Button, { ButtonLink } from "../../../components/Button";
import { Input, Select } from "../../../components/FormFields";
import { formatNumber, formatToman, toPersianDigits } from "../../../utils/persianFormat";
import { addToCart } from "../../../hooks/useCart";

function useProducts(featured = false) {
  return useQuery({ queryKey: ["products", featured], queryFn: () => apiClient.get(`/products/${featured ? '?featured=1' : ''}`).then(r => r.data) });
}
export function ProductPhoto({ product, image, imageAlt, className = "" }) {
  const src = image || product.images?.[0]?.image;
  return <div className={`product-photo ${className}`}>{src ? <img src={src} alt={imageAlt || product.title} loading="lazy" /> : <div className="product-photo-empty"><Package size={36} strokeWidth={1.25} /><span>تصویر به‌زودی</span></div>}</div>;
}
export function BundlePromotion() {
  const query = useProducts(true);
  if (query.isError) return <div role="alert" className="mb-6 text-sm text-ink-600">پک‌های پیشنهادی دریافت نشد. <Button variant="ghost" onClick={() => query.refetch()}>تلاش دوباره</Button></div>;
  if (!query.data?.length) return null;
  const [lead, ...others] = query.data;
  return <section className="bundle-promotion" aria-label="پک‌های تلبوک">
    <div className="bundle-feature"><Link to={`/products/${lead.id}`} tabIndex={-1} aria-hidden="true"><ProductPhoto product={lead} /></Link><div className="bundle-feature-copy"><h2>{toPersianDigits(lead.title)}</h2><p>{lead.description || 'یک انتخاب آماده از میان محصولات تلبوک؛ محتویات پک را ببین و سفارش بده.'}</p><ul>{lead.components.slice(0, 4).map((c, i) => <li key={i}>{formatNumber(c.quantity)} × {toPersianDigits(c.title)}</li>)}</ul><strong>{formatToman(lead.price)}</strong><ButtonLink to={`/products/${lead.id}`}>مشاهده و خرید پک<ArrowLeft size={18} /></ButtonLink></div></div>
    {others.length > 0 && <div className="bundle-other">{others.map(p => <Link key={p.id} to={`/products/${p.id}`}><span>{toPersianDigits(p.title)}</span><span>{formatToman(p.price)}</span><ArrowLeft size={18} /></Link>)}</div>}
  </section>;
}
export default function Products() {
  const query = useProducts();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const categories = [...new Set((query.data || []).map(p => p.category))];
  const products = (query.data || []).filter(p => (!category || p.category === category) && p.title.includes(search));
  return <div><div className="section-heading"><div><h1 className="page-title">پک‌ها و همراه‌های کتاب</h1><p>یک پک آماده انتخاب کن، یا همراه‌های دلخواهت را جداگانه بردار.</p></div><ButtonLink to="/cart" variant="secondary">سبد خرید</ButtonLink></div>
    <div className="product-filters"><Input label="جستجوی محصول" value={search} onChange={e => setSearch(e.target.value)} /><Select label="دسته‌بندی" value={category} onChange={e => setCategory(e.target.value)}><option value="">همه محصولات</option>{categories.map(c => <option key={c}>{c}</option>)}</Select></div>
    <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>{products.length ? <div className="product-grid">{products.map(product => <article key={product.id} className="product-tile"><Link to={`/products/${product.id}`}><ProductPhoto product={product} /><h2>{toPersianDigits(product.title)}</h2></Link><p className="text-sm text-ink-500">{product.category} · {product.available ? product.needs_sourcing ? 'تهیه پس از سفارش' : 'آماده در فروشگاه' : 'ناموجود'}</p><strong>{formatToman(product.price)}</strong><ButtonLink variant="secondary" to={`/products/${product.id}`}>{product.is_bundle ? 'دیدن محتویات پک' : 'مشاهده و خرید'}</ButtonLink></article>)}</div> : <EmptyState title="محصولی پیدا نشد" description="دسته‌بندی یا عبارت جستجو را تغییر بده؛ محصولات تازه پس از انتشار اینجا نمایش داده می‌شوند." />}</QueryBoundary>
  </div>;
}
export function ProductDetail() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["product", id], queryFn: () => apiClient.get(`/products/${id}/`).then(r => r.data) });
  const [selected, setSelected] = useState(null);
  const navigate = useNavigate();
  const product = query.data;
  const currentImage = product?.images.find(image => image.id === selected) || product?.images[0];
  return <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>{product && <div><ButtonLink to="/products" variant="ghost">بازگشت به محصولات</ButtonLink><div className="product-detail"><div><figure><ProductPhoto product={product} image={currentImage?.image} imageAlt={currentImage?.caption} />{currentImage?.caption && <figcaption className="mt-3 text-sm text-ink-600">{currentImage.caption}</figcaption>}</figure><div className="product-thumbnails">{product.images.map((image, i) => <button key={image.id} aria-label={`نمایش تصویر ${toPersianDigits(i + 1)}`} aria-pressed={currentImage?.id === image.id} onClick={() => setSelected(image.id)}><img src={image.image} alt={image.caption || product.title} /></button>)}</div></div><div className="product-description"><h1 className="page-title">{toPersianDigits(product.title)}</h1><p className="whitespace-pre-line">{product.description}</p><p className="text-sm text-ink-600">{product.available ? product.needs_sourcing ? `تهیه پس از پرداخت؛ زمان تقریبی ${toPersianDigits(product.estimated_days)} روز` : 'آماده در فروشگاه' : 'فعلاً ناموجود'}</p><strong className="product-price">{formatToman(product.price)}</strong><Button disabled={!product.available} onClick={() => { addToCart({ product_id: product.id, title: product.title, price: product.price }); navigate('/cart'); }}>افزودن به سبد خرید</Button><p className="text-sm text-ink-500">ارسال پس از آماده‌شدن یا نگهداری روی قفسه؛ در مرحله بعد انتخاب می‌کنی. {product.is_bundle && 'محتویات این پک ثابت است و با هم ارسال می‌شود.'}</p>
      {product.components.length > 0 && <section className="bundle-contents"><h2>داخل این پک</h2>{product.components.map((c, i) => <div key={i}><span>{formatNumber(c.quantity)} × {toPersianDigits(c.title)}</span>{c.sold_separately && <Link className="action-link" to={c.product ? `/products/${c.product}` : `/books/${c.book_id}`}>خرید جداگانه</Link>}</div>)}</section>}
      {product.specifications && <section><h2 className="section-title">مشخصات</h2><p className="whitespace-pre-line">{toPersianDigits(product.specifications)}</p></section>}</div></div></div>}</QueryBoundary>;
}
