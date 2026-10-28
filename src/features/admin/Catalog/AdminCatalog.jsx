import { useQuery } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAdminCatalog, usePublishers, useCatalogMutation } from "../../../hooks/useCatalogAdmin";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { Input, Select } from "../../../components/FormFields";
import Button, { ButtonLink } from "../../../components/Button";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import AdminPagination from "../../../components/AdminPagination";
import BookMetadataForm from "./BookMetadataForm";
import { formatNumber, toPersianDigits } from "../../../utils/persianFormat";
export default function AdminCatalog() {
  const navigate=useNavigate(); const [params,setParams]=useSearchParams();
  const [search,setSearch]=useState(params.get("q")||""); const [query,setQuery]=useState(search); const [page,setPage]=useState(1); const [creating,setCreating]=useState(false);
  useEffect(()=>{const timer=setTimeout(()=>{setQuery(search);setPage(1);},250);return()=>clearTimeout(timer);},[search]);
  const publisher=params.get("publisher_id")||""; const review=params.get("needs_review")||"";
  const books=useAdminCatalog({q:query,page,publisher_id:publisher||undefined,needs_review:review||undefined,homepage_only:params.get("homepage_only")||undefined}); const publishers=usePublishers();
  const home = useQuery({queryKey:["admin","homepage-selection"],queryFn:()=>apiClient.get("/catalog/admin/homepage/").then(r=>r.data)});
  const chooseHome = useCatalogMutation(payload=>apiClient.patch("/catalog/admin/homepage/",payload));
  const clearHome = useCatalogMutation(()=>apiClient.delete("/catalog/admin/homepage/"));
  const create=useCatalogMutation(payload=>apiClient.post("/catalog/admin/books/",payload).then(r=>r.data),data=>navigate(`/admin/books/${data.id}`));
  const filter=(key,value)=>{const next=new URLSearchParams(params);if(value)next.set(key,value);else next.delete(key);setParams(next);setPage(1);};
  return <div className="space-y-6"><div className="section-heading"><div><h1 className="page-title">کتاب‌ها و نسخه‌ها</h1><p>اطلاعات مشترک کتاب و نسخه‌های ناشران را از یک‌جا مدیریت کنید.</p></div><Button onClick={()=>setCreating(!creating)}>{creating?"بستن فرم":"کتاب تازه"}</Button></div>
    <section className="surface space-y-3" aria-labelledby="homepage-selection-title"><h2 id="homepage-selection-title" className="section-title">کتاب‌های «در فهرست تلبوک»</h2><p>{home.data?.selected_count ? `${formatNumber(home.data.selected_count)} کتاب برای صفحه اول انتخاب شده است.` : "تا وقتی کتابی انتخاب نکرده‌اید، ۱۲ کتاب به‌صورت تصادفی نمایش داده می‌شوند."} با دکمه کنار هر کتاب، انتخاب صفحه اول را تغییر دهید.</p><div className="flex flex-wrap gap-3"><Button variant="secondary" onClick={()=>filter("homepage_only",params.get("homepage_only")?"":"true")}>{params.get("homepage_only")?"نمایش همه کتاب‌ها":"نمایش انتخاب‌های صفحه اول"}</Button><Button variant="ghost" disabled={!home.data?.selected_count||clearHome.isPending} onClick={()=>clearHome.mutate()}>پاک‌کردن انتخاب‌ها و نمایش تصادفی</Button></div>{(home.isError||chooseHome.isError||clearHome.isError)&&<p role="alert" className="field-error">{apiErrorMessage(home.error||chooseHome.error||clearHome.error)}</p>}</section>
    {creating && <section className="surface"><h2 className="section-title mb-4">ثبت کتاب تازه</h2><BookMetadataForm onSave={payload=>create.mutate(payload)} pending={create.isPending} error={create.isError?apiErrorMessage(create.error):""} /></section>}
    <div className="catalog-admin-filters"><Input label="جست‌وجوی عنوان، نویسنده یا شابک" value={search} onChange={e=>setSearch(e.target.value)} /><Select label="ناشر" value={publisher} onChange={e=>filter("publisher_id",e.target.value)}><option value="">همه ناشران</option>{publishers.data?.map(pub=><option key={pub.id} value={pub.id}>{pub.name}</option>)}</Select><Select label="وضعیت بازبینی" value={review} onChange={e=>filter("needs_review",e.target.value)}><option value="">همه کتاب‌ها</option><option value="true">نیازمند بازبینی</option><option value="false">تأیید شده</option></Select></div>
    <QueryBoundary isLoading={books.isLoading} isError={books.isError} onRetry={books.refetch}>{books.data?.results.length ? <div className="management-list">{books.data.results.map(book=><div key={book.id} className="management-row"><div><h2>{toPersianDigits(book.title)}</h2><p>{book.authors.join("، ")||"نویسنده ثبت نشده"}</p><small>{book.editions.map(e=>e.publisher_name).join("، ")||"هنوز نسخه‌ای از ناشر ثبت نشده"}</small></div><div className="management-row-actions"><span>{book.needs_review?"نیازمند بازبینی":`${formatNumber(book.edition_count)} نسخه ناشر`}</span><Button variant="ghost" aria-pressed={book.homepage_selected} disabled={chooseHome.isPending||book.needs_review} onClick={()=>chooseHome.mutate({book_id:book.id,selected:!book.homepage_selected})}>{book.homepage_selected?"حذف از صفحه اول":"انتخاب برای صفحه اول"}</Button><ButtonLink variant="secondary" to={`/admin/books/${book.id}`}>ویرایش کتاب</ButtonLink></div></div>)}</div>:<EmptyState title="کتابی با این مشخصات پیدا نشد" description="عبارت جست‌وجو یا فیلترها را تغییر دهید، یا کتاب تازه ثبت کنید." />}<AdminPagination data={books.data} page={page} onChange={setPage} /></QueryBoundary>
  </div>;
}
