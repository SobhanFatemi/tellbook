import { useState } from "react";
import { Input, Textarea } from "../../../components/FormFields";
import Button from "../../../components/Button";
export default function BookMetadataForm({ initial={}, onSave, pending, error }) {
  const [form,setForm]=useState({...initial,authors:(initial.authors||[]).join("، ")});
  const field=key=>({value:form[key]??"",onChange:e=>setForm({...form,[key]:e.target.value})});
  return <form className="space-y-4" onSubmit={e=>{e.preventDefault();onSave({title:form.title.trim(),authors:form.authors.split(/[،,\n]/).map(s=>s.trim()).filter(Boolean),description:form.description||"",category:form.category||"",subcategory:form.subcategory||""});}}>
    <Input label="عنوان کتاب" maxLength={500} localizeDigits required {...field("title")} /><Input label="نویسنده‌ها (با ویرگول جدا کنید)" {...field("authors")} />
    <div className="grid sm:grid-cols-2 gap-4"><Input label="دسته‌بندی" maxLength={200} {...field("category")} /><Input label="زیرگروه" maxLength={200} {...field("subcategory")} /></div><Textarea label="توضیحات کتاب" rows={6} {...field("description")} />
    <p className="text-sm text-ink-500">اطلاعاتی که اینجا ذخیره می‌کنید در ورودهای بعدی اکسل حفظ می‌شوند. ناشر، مترجم و قیمت را در بخش نسخه‌های ناشران تغییر دهید.</p>
    {error && <p role="alert" className="field-error">{error}</p>}<Button type="submit" disabled={pending}>{pending?"در حال ذخیره…":initial.id?"ذخیره اطلاعات کتاب":"ثبت کتاب"}</Button>
  </form>;
}
