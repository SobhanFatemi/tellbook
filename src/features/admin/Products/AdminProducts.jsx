import FileDropzone from "../../../components/FileDropzone";
import { useState } from "react";
import { Plus, PackagePlus } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { Input, Select, Textarea } from "../../../components/FormFields";
import Button, { ButtonLink } from "../../../components/Button";
import { QueryBoundary, EmptyState } from "../../../components/Feedback";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";

const initial = { title: '', category: '', description: '', specifications: '', price: '', lead_days: 0, is_active: false, sold_separately: true, is_bundle: false, featured: false, priority: 0, components: [] };
export default function AdminProducts() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['admin', 'products'], queryFn: () => apiClient.get('/products/admin/').then(r => r.data) });
  const [editing, setEditing] = useState(null);
  const [search, setSearch] = useState('');
  const refresh = () => { client.invalidateQueries({ queryKey: ['admin', 'products'] }); client.invalidateQueries({ queryKey: ['products'] }); client.invalidateQueries({ queryKey: ['product'] }); };
  const createActions = <div className="admin-product-create-actions" role="group" aria-label="افزودن محصول یا پک">
    <Button onClick={() => setEditing({ ...initial })}><Plus size={18} aria-hidden="true" />محصول تازه</Button>
    <Button variant="secondary" onClick={() => setEditing({ ...initial, is_bundle: true, category: 'پک' })}><PackagePlus size={18} aria-hidden="true" />پک تازه</Button>
  </div>;
  return <div>
    <div className="section-heading"><div><h1 className="page-title">محصولات و پک‌ها</h1><p>همراه‌های کتاب را ثبت کن، بعد از ترکیب آن‌ها یک پک بساز.</p></div>{editing && createActions}</div>
    {editing ? <Editor key={editing.id || String(editing.is_bundle)} original={editing} products={query.data || []} onClose={() => setEditing(null)} onSave={product => { refresh(); setEditing(product); }} refresh={refresh} /> : <>
      <div className="admin-products-toolbar">
        <Input label="جستجوی محصولات" value={search} onChange={e => setSearch(e.target.value)} />
        {createActions}
      </div>
      <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>{query.data?.length ? <div className="admin-product-list">{query.data.filter(p => p.title.includes(search)).map(p => <article key={p.id}><div>{p.images[0] && <img src={p.images[0].image} alt="" />}<div><h2>{toPersianDigits(p.title)}</h2><p>{p.category} · {p.is_active ? 'منتشرشده' : 'پیش‌نویس / غیرفعال'}{p.featured && ' · نمایش در صفحه اول'}</p><p>{p.is_bundle ? 'پک با محتویات ثابت' : 'آماده‌سازی پس از سفارش'}</p></div></div><div><strong>{formatToman(p.price)}</strong><Button variant="secondary" onClick={() => setEditing(p)}>ویرایش</Button></div></article>)}</div> : <EmptyState title="اولین محصول را ثبت کن" description="بوکمارک، پوستر، کارت پستال یا هر همراه دیگر؛ سپس از همین محصولات پک بساز." />}</QueryBoundary></>}
  </div>;
}
function Editor({ original, products, onClose, onSave, refresh }) {
  const [form, setForm] = useState(original);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [bookQuery, setBookQuery] = useState('');
  const [component, setComponent] = useState('');
  const [file, setFile] = useState(null);
  const [caption, setCaption] = useState('');
  const set = (key, value) => { setForm(f => ({ ...f, [key]: value })); setSaved(''); };
  const editions = useQuery({ queryKey: ['admin', 'bundle-editions', bookQuery], enabled: bookQuery.trim().length >= 2, queryFn: () => apiClient.get('/products/admin/editions/', { params: { q: bookQuery } }).then(r => r.data) });
  const save = useMutation({ mutationFn: () => {
    const payload = Object.fromEntries(Object.keys(initial).map(k => [k, form[k]]));
    if (form.id) payload.expected_updated_at = form.updated_at;
    payload.components = form.components.map(c => ({ product: c.product || null, edition: c.edition || null, quantity: Number(c.quantity) }));
    return (form.id ? apiClient.patch(`/products/admin/${form.id}/`, payload) : apiClient.post('/products/admin/', payload)).then(r => r.data);
  }, onSuccess: product => { setForm(product); setSaved('تغییرات ذخیره شد.'); onSave(product); }, onError: e => setError(apiErrorMessage(e)) });
  const images = useMutation({ mutationFn: async ({ remove }) => {
    if (remove) await apiClient.delete(`/products/admin/${form.id}/images/${remove}/`);
    else { const data = new FormData(); data.append('image', file); data.append('caption', caption); await apiClient.post(`/products/admin/${form.id}/images/`, data); }
    const { data } = await apiClient.get('/products/admin/');
    return data.find(p => p.id === form.id);
  }, onSuccess: p => { setForm(f => ({ ...f, images: p.images })); setFile(null); setCaption(''); refresh(); setSaved('تصاویر به‌روز شد.'); }, onError: e => setError(apiErrorMessage(e)) });
  const add = row => {
    if (form.components.some(c => (row.product && c.product === row.product) || (row.edition && c.edition === row.edition))) return;
    set('components', [...form.components, { ...row, quantity: 1 }]);
  };
  return <div className="product-editor"><div className="flex flex-wrap justify-between gap-3"><h2 className="section-title">{form.id ? `ویرایش ${form.title}` : form.is_bundle ? 'ساخت پک تازه' : 'ثبت محصول تازه'}</h2><Button variant="ghost" onClick={onClose}>بازگشت به فهرست</Button></div>
    <form onSubmit={e => { e.preventDefault(); setError(''); save.mutate(); }} className="space-y-6">
      <div className="product-fields"><Input label="نام محصول یا پک" value={form.title} onChange={e => set('title', e.target.value)} required maxLength={250} /><Input label="دسته‌بندی" list="product-categories" value={form.category} onChange={e => set('category', e.target.value)} required maxLength={80} /><datalist id="product-categories">{['پوستر', 'بوکمارک', 'کارت پستال', 'بوک ترکر', 'پک'].map(c => <option key={c} value={c} />)}</datalist></div>
      <Textarea label="معرفی محصول" value={form.description} onChange={e => set('description', e.target.value)} rows={4} />
      <Textarea label="مشخصات (اندازه، جنس، تعداد و…)" value={form.specifications} onChange={e => set('specifications', e.target.value)} rows={3} />
      <div className="product-fields"><Input groupDigits label={form.is_bundle ? 'قیمت کل پک (تومان)' : 'قیمت فروش (تومان)'} type="number" min={1} max={99999999999} value={form.price} onChange={e => set('price', e.target.value)} required />
      {!form.is_bundle && <Input label="زمان تقریبی تهیه (روز)" type="number" min={0} max={365} value={form.lead_days} onChange={e => set('lead_days', e.target.value)} required />}</div>
      {form.is_bundle && <section className="bundle-builder"><h3 className="section-title">محتویات ثابت پک</h3><p>کتاب‌ها را با نسخه ناشر انتخاب کن. محصولات داخل پک باید فعال باشند؛ فروش جداگانه آن‌ها اختیاری است. با غیرفعال‌کردن هر قلم، پک هم غیرقابل سفارش می‌شود.</p>
        {form.components.map((c, i) => <div className="bundle-builder-row" key={`${c.product || 'e'}-${c.edition || i}`}><span>{c.title}</span><Input label={`تعداد ${c.title}`} type="number" min={1} max={100} required value={c.quantity} onChange={e => set('components', form.components.map((row, index) => index === i ? { ...row, quantity: e.target.value } : row))} /><Button variant="ghost" onClick={() => set('components', form.components.filter((_, index) => index !== i))}>حذف</Button></div>)}
        <div className="product-fields"><Select label="افزودن محصول به پک" value={component} onChange={e => setComponent(e.target.value)}><option value="">انتخاب محصول</option>{products.filter(p => !p.is_bundle).map(p => <option key={p.id} value={p.id}>{p.title}{!p.is_active ? ' (غیرفعال)' : ''}</option>)}</Select><Button variant="secondary" disabled={!component} onClick={() => { const p = products.find(p => p.id === Number(component)); add({ product: p.id, title: p.title }); setComponent(''); }}>افزودن محصول</Button></div>
        <Input label="افزودن کتاب؛ جستجوی عنوان یا شابک" value={bookQuery} onChange={e => setBookQuery(e.target.value)} />
        {editions.isFetching && <p role="status">در حال جستجوی نسخه‌ها…</p>}{editions.isError && <p role="alert">جستجو انجام نشد. <Button variant="ghost" onClick={() => editions.refetch()}>تلاش دوباره</Button></p>}
        {bookQuery.length >= 2 && editions.data?.length === 0 && <p>نسخه فعالی با این نام پیدا نشد.</p>}
        {bookQuery.length >= 2 && editions.data?.map(e => <div className="edition-choice" key={e.id}><span>{e.title} · {formatToman(e.price)}</span><Button variant="secondary" onClick={() => { add({ edition: e.id, title: e.title }); setBookQuery(''); }}>افزودن به پک</Button></div>)}
      </section>}
      <fieldset className="product-publishing"><legend className="section-title">انتشار و نمایش</legend><label><input type="checkbox" checked={form.is_active} onChange={e => set('is_active', e.target.checked)} />فعال و قابل سفارش</label><label><input type="checkbox" checked={form.sold_separately} onChange={e => set('sold_separately', e.target.checked)} />فروش جداگانه در فهرست محصولات</label>{form.is_bundle && <><label><input type="checkbox" checked={form.featured} onChange={e => set('featured', e.target.checked)} />نمایش در بنر صفحه اول، زمانی که قابل خرید است</label><Input label="اولویت نمایش (عدد کمتر، بالاتر)" type="number" min={0} max={32767} value={form.priority} onChange={e => set('priority', e.target.value)} /></>}</fieldset>
      {error && <p role="alert" className="text-red-700">{error}</p>}{saved && <p role="status" className="text-green-800">{saved}</p>}<div className="flex flex-wrap gap-3"><Button type="submit" disabled={save.isPending || images.isPending}>{save.isPending ? 'در حال ذخیره…' : 'ذخیره محصول'}</Button>{form.id && form.is_active && form.sold_separately && <ButtonLink to={`/products/${form.id}`} variant="secondary">دیدن در فروشگاه</ButtonLink>}</div>
    </form>
    <section className="product-image-editor"><h2 className="section-title">عکس‌های محصول</h2><p>اولین تصویر، عکس اصلی محصول و بنر است. عکس اصلی بدون نوشته‌های تلگرام را بارگذاری کن؛ تا ۱۲ تصویر.</p>{!form.id ? <p>ابتدا محصول را ذخیره کن، سپس عکس‌ها را اضافه کن.</p> : <><div className="product-image-list">{form.images?.map(image => <figure key={image.id}><img src={image.image} alt={image.caption || form.title} /><figcaption>{image.caption}</figcaption><Button variant="ghost" disabled={images.isPending} onClick={() => { setError(''); images.mutate({ remove: image.id }); }}>حذف تصویر</Button></figure>)}</div><form onSubmit={e => { e.preventDefault(); setError(''); images.mutate({}); }} className="space-y-3"><FileDropzone label="انتخاب تصویر محصول" value={file} onChange={setFile} maxSizeMB={8} /><Input label="توضیح تصویر" value={caption} onChange={e => setCaption(e.target.value)} maxLength={250} /><Button type="submit" variant="secondary" disabled={!file || images.isPending || save.isPending}>{images.isPending ? 'در حال بارگذاری…' : 'افزودن تصویر'}</Button></form></>}</section>
  </div>;
}
