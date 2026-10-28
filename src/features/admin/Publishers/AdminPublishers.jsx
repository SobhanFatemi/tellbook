import { useState } from "react";
import { usePublishers, useCatalogMutation } from "../../../hooks/useCatalogAdmin";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { Input } from "../../../components/FormFields";
import Button, { ButtonLink } from "../../../components/Button";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import { formatNumber, toPersianDigits } from "../../../utils/persianFormat";
export default function AdminPublishers() {
  const publishers=usePublishers();const [editing,setEditing]=useState(null);const [search,setSearch]=useState("");const [notice,setNotice]=useState("");
  const rows=publishers.data?.filter(pub=>pub.name.includes(search));
  return <div className="space-y-6"><div className="section-heading"><div><h1 className="page-title">ناشران</h1><p>اطلاعات ناشر، زمان معمول تهیه و فایل‌های کتاب‌هایش.</p></div><Button onClick={()=>{setNotice("");setEditing({name:"",typical_lead_days:5});}}>ناشر تازه</Button></div>
    {notice && <p role="status" className="text-green-800">{notice}</p>}{editing && <PublisherForm key={editing.id||"new"} initial={editing} onClose={()=>setEditing(null)} onSaved={()=>{setEditing(null);setNotice("اطلاعات ناشر ذخیره شد.");}} />}
    <Input label="جست‌وجوی ناشر" value={search} onChange={e=>setSearch(e.target.value)} />
    <QueryBoundary isLoading={publishers.isLoading} isError={publishers.isError} onRetry={publishers.refetch}>{rows?.length?<div className="management-list">{rows.map(pub=><div className="management-row" key={pub.id}><div><h2>{pub.name}</h2><p>{formatNumber(pub.edition_count)} نسخه · زمان معمول تهیه {toPersianDigits(pub.typical_lead_days)} روز</p></div><div className="management-row-actions"><ButtonLink variant="ghost" to={`/admin/books?publisher_id=${pub.id}`}>کتاب‌های ناشر</ButtonLink><ButtonLink variant="ghost" to={`/admin/imports?publisher_id=${pub.id}`}>فایل‌های اکسل</ButtonLink><Button variant="secondary" onClick={()=>{setNotice("");setEditing(pub);}}>ویرایش ناشر</Button></div></div>)}</div>:<EmptyState title="ناشری پیدا نشد" description="ناشر تازه را ثبت کنید یا عبارت جست‌وجو را تغییر دهید." />}</QueryBoundary>
  </div>;
}
function PublisherForm({initial,onClose,onSaved}) {
  const [form,setForm]=useState(initial);
  const save=useCatalogMutation(payload=>initial.id?apiClient.patch(`/publishers/${initial.id}/`,payload):apiClient.post("/publishers/",payload),onSaved);
  return <form className="surface space-y-4" onSubmit={e=>{e.preventDefault();save.mutate({name:form.name.trim(),typical_lead_days:form.typical_lead_days});}}><h2 className="section-title">{initial.id?"ویرایش ناشر":"ثبت ناشر"}</h2><Input label="نام ناشر" maxLength={300} value={form.name} required onChange={e=>setForm({...form,name:e.target.value})} /><Input label="زمان معمول تهیه (روز)" type="number" min="0" max="365" value={form.typical_lead_days} required onChange={e=>setForm({...form,typical_lead_days:e.target.value})} />{save.isError && <p role="alert" className="field-error">{apiErrorMessage(save.error)}</p>}<div className="flex gap-2"><Button type="submit" disabled={save.isPending}>ذخیره ناشر</Button><Button variant="ghost" onClick={onClose}>انصراف</Button></div></form>;
}
