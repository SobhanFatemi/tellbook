import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { useCatalogMutation, usePublishers } from "../../../hooks/useCatalogAdmin";
import { Input, Select } from "../../../components/FormFields";
import Button, { ButtonLink } from "../../../components/Button";
import { QueryBoundary } from "../../../components/Feedback";
import FileDropzone from "../../../components/FileDropzone";
import { BookCover } from "../../../components/BookCard";
import { formatToman, toPersianDigits } from "../../../utils/persianFormat";
import BookMetadataForm from "./BookMetadataForm";
export default function AdminBookEditor() {
  const {id}=useParams();const [editing,setEditing]=useState(null);const [notice,setNotice]=useState("");
  const book=useQuery({queryKey:["admin","book",id],queryFn:()=>apiClient.get(`/catalog/admin/books/${id}/`).then(r=>r.data)});
  const save=useCatalogMutation(payload=>apiClient.patch(`/catalog/${id}/edit/`,payload),()=>setNotice("اطلاعات کتاب ذخیره شد."));
  return <div className="space-y-6"><ButtonLink to="/admin/books" variant="ghost">بازگشت به کتاب‌ها</ButtonLink><QueryBoundary isLoading={book.isLoading} isError={book.isError} onRetry={book.refetch}>{book.data && <><h1 className="page-title">{toPersianDigits(book.data.title)}</h1>{notice && <p role="status" className="text-green-800">{notice}</p>}{book.data.needs_review && <p className="text-amber-900">این کتاب در صف بازبینی است. <ButtonLink to="/admin/books/review" variant="ghost">رفتن به صف بازبینی</ButtonLink></p>}
    <section className="surface"><h2 className="section-title mb-4">اطلاعات مشترک کتاب</h2><BookMetadataForm key={book.data.id} initial={book.data} onSave={payload=>{setNotice("");save.mutate(payload);}} pending={save.isPending} error={save.isError?apiErrorMessage(save.error):""} /></section>
    <section><div className="section-heading"><div><h2>نسخه‌های ناشران</h2><p>هر ناشر مترجم، تصویر جلد و قیمت خودش را دارد. قیمت‌ها به تومان هستند.</p></div><Button onClick={()=>setEditing({})}>افزودن نسخه ناشر</Button></div>
      {editing && <EditionForm key={editing.id||"new"} initial={editing} book={book.data} onClose={()=>setEditing(null)} onSaved={()=>{setEditing(null);setNotice("نسخه ناشر ذخیره شد.");}} />}
      <div className="management-list">{book.data.editions.map(edition=><div className="management-row edition-row" key={edition.id}><BookCover src={edition.cover} title={book.data.title} /><div><h3>{edition.publisher_name}</h3><p>{edition.translators.length?`ترجمه: ${edition.translators.join("، ")}`:"مترجم ثبت نشده"}</p><p>{formatToman(edition.price)} · {edition.is_active?"قابل سفارش":"غیرفعال"}</p>{edition.isbn && <small>شابک: <bdi>{toPersianDigits(edition.isbn)}</bdi></small>}</div><Button variant="secondary" onClick={()=>setEditing(edition)}>ویرایش نسخه</Button></div>)}{!book.data.editions.length && <p className="py-5 text-ink-500">برای این کتاب هنوز نسخه ناشری ثبت نشده است.</p>}</div>
    </section></>}</QueryBoundary></div>;
}
function EditionForm({initial,book,onClose,onSaved}) {
  const [form,setForm]=useState({...initial,translator_names:initial.translators?.join("، ")||"",is_active:initial.is_active??true});const [cover,setCover]=useState(null);const [clearCover,setClearCover]=useState(false);const publishers=usePublishers();
  const save=useCatalogMutation(payload=>initial.id?apiClient.patch(`/publishers/editions/${initial.id}/edit/`,payload):apiClient.post("/catalog/admin/editions/",payload),onSaved);
  const field=key=>({value:form[key]??"",onChange:e=>setForm({...form,[key]:e.target.value})});
  const submit=e=>{e.preventDefault();const data=new FormData();if(!initial.id){data.append("book",book.id);data.append("publisher",form.publisher||"");}for(const key of ["price","cost_price","isbn","national_barcode","sku","cover_type","cover_image_url","print_year","page_count","volume_count","print_run","weight"])data.append(key,form[key]??"");data.append("is_active",String(form.is_active));data.append("translator_names",JSON.stringify(form.translator_names.split(/[،,\n]/).map(v=>v.trim()).filter(Boolean)));data.append("clear_cover",String(clearCover));if(cover)data.append("cover_image_override",cover);save.mutate(data);};
  return <form className="surface space-y-4 mb-6" onSubmit={submit}><h3 className="section-title">{initial.id?`ویرایش نسخه ${initial.publisher_name}`:"نسخه تازه"}</h3>
    {!initial.id && <Select label="ناشر نسخه" required {...field("publisher")}><option value="">انتخاب ناشر</option>{publishers.data?.filter(pub=>!book.editions.some(ed=>ed.publisher===pub.id)).map(pub=><option key={pub.id} value={pub.id}>{pub.name}</option>)}</Select>}
    {initial.price_review_note && <p role="note" className="text-amber-900">{initial.price_review_note} ذخیره نسخه به‌معنای تأیید قیمت واردشده است.</p>}
    <Input label="مترجم‌ها (با ویرگول جدا کنید)" {...field("translator_names")} />
    <div className="grid sm:grid-cols-2 gap-4"><Input groupDigits label="قیمت فروش (تومان)" type="number" min="0" required {...field("price")} /><Input groupDigits label="قیمت خرید (تومان، اختیاری)" type="number" min="0" {...field("cost_price")} /><Input label="شابک" localizeDigits dir="ltr" maxLength={20} {...field("isbn")} /><Input label="کد کالا نزد ناشر" localizeDigits {...field("sku")} /><Input label="بارکد ملی" localizeDigits dir="ltr" {...field("national_barcode")} /><Input label="نوع جلد" {...field("cover_type")} /><Input label="سال چاپ" type="number" min="0" {...field("print_year")} /><Input label="تعداد صفحات" type="number" min="0" {...field("page_count")} /><Input label="تعداد جلد" type="number" min="0" {...field("volume_count")} /><Input label="نوبت چاپ" type="number" min="0" {...field("print_run")} /><Input label="وزن (کیلوگرم)" type="number" min="0" step="0.001" {...field("weight")} /></div>
    <div className="edition-cover-editor"><div><FileDropzone label="بارگذاری تصویر جلد" value={cover} onChange={file=>{setCover(file);setClearCover(false);}} /></div><div><Input label="نشانی اینترنتی تصویر جلد (اختیاری)" type="url" dir="ltr" {...field("cover_image_url")} /><p className="text-sm text-ink-500 mt-3">تصویر بارگذاری‌شده بر نشانی اینترنتی اولویت دارد و با اکسل عوض نمی‌شود.</p>{initial.cover_image_override && <label className="flex items-center gap-2 mt-3"><input type="checkbox" checked={clearCover} onChange={e=>{setClearCover(e.target.checked);setCover(null);}} />حذف تصویر بارگذاری‌شده</label>}</div></div>
    <label className="flex items-center gap-2"><input type="checkbox" checked={form.is_active} onChange={e=>setForm({...form,is_active:e.target.checked})} />این نسخه قابل سفارش است</label><p className="text-sm text-ink-500">تغییر قیمت روی سفارش‌های ثبت‌شده اثر ندارد. تغییر قیمت و وضعیت در فایل بعدی، پیش از اعمال به شما نشان داده می‌شود.</p>
    {save.isError && <p role="alert" className="field-error">{apiErrorMessage(save.error)}</p>}<div className="flex flex-wrap gap-2"><Button type="submit" disabled={save.isPending}>ذخیره نسخه ناشر</Button><Button variant="ghost" onClick={onClose}>انصراف</Button></div>
  </form>;
}
