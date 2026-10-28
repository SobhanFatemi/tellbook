import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../../api/client";
import { ButtonLink } from "../../../components/Button";
import { QueryBoundary, EmptyState } from "../../../components/Feedback";
import AdminPagination from "../../../components/AdminPagination";
import { formatNumber } from "../../../utils/persianFormat";
import { formatJalaliShort } from "../../../utils/jalali";
import ImportWizard from "./ImportWizard";
import BatchReview from "./BatchReview";
import { statusLabels } from "./importLabels";
export default function AdminImports(){const {batchId}=useParams();return batchId?<BatchReview id={batchId}/>:<ImportWorkspace/>;}
function ImportWorkspace(){
  const [params]=useSearchParams();const publisher=params.get("publisher_id")||"";const [page,setPage]=useState(1);
  const history=useQuery({queryKey:["admin","import-history",publisher,page],queryFn:()=>apiClient.get("/publishers/import-batches/",{params:{page,publisher_id:publisher||undefined}}).then(r=>r.data),refetchInterval:10000});
  return <div className="space-y-7"><h1 className="page-title">فایل‌های اکسل</h1><p className="text-ink-500">فایل را بخوانید، ستون‌ها و واحد قیمت را مشخص کنید و تغییرات را پیش از اعمال ببینید. بارگذاری فایل به‌تنهایی، کتاب‌ها را تغییر نمی‌دهد.</p>
    <ImportWizard initialPublisher={publisher}/>
    <section><h2 className="section-title mb-4">تاریخچه ورود فایل</h2><QueryBoundary isLoading={history.isLoading} isError={history.isError} onRetry={history.refetch}>{history.data?.results.length?<div className="management-list">{history.data.results.map(batch=><div className="management-row" key={batch.id}><div><h3>{batch.publisher_name} — {batch.profile_label||"قالب ناشر"}</h3><p className="break-all">{batch.filename}</p><small>{formatJalaliShort(batch.created_at)} · {formatNumber(batch.total_rows)} ردیف</small></div><div className="management-row-actions"><span>{statusLabels[batch.status]}</span><ButtonLink variant="secondary" to={`/admin/imports/${batch.id}`}>مشاهده و بررسی</ButtonLink></div></div>)}</div>:<EmptyState title="هنوز فایلی وارد نشده" />}<AdminPagination data={history.data} page={page} onChange={setPage}/></QueryBoundary></section>
  </div>;
}
