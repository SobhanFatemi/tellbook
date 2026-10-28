import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, apiErrorMessage } from "../../../api/client";
import { Input, Textarea } from "../../../components/FormFields";
import Button from "../../../components/Button";
import BookPostCard from "../../../components/BookPostCard";
import { EmptyState, QueryBoundary } from "../../../components/Feedback";
import { toPersianDigits } from "../../../utils/persianFormat";
const blank = {title:"", body:"", books:[], images:[], is_published:false};
export default function AdminPosts() {
  const query = useQuery({queryKey:["admin","posts"], queryFn:() => apiClient.get("/catalog/admin/posts/").then(r=>r.data)});
  const [editing, setEditing] = useState(null);
  return <div className="space-y-6"><div className="section-heading"><div><h1 className="page-title">معرفی کتاب</h1><p>عکس‌ها و نوشته‌های دایانا، زیر فهرست کتاب‌های صفحه اول.</p></div><Button onClick={() => setEditing({...blank})}>معرفی تازه</Button></div>
    {editing && <PostEditor key={editing.id || "new"} initial={editing} onClose={() => setEditing(null)} />}
    <QueryBoundary isLoading={query.isLoading} isError={query.isError} onRetry={query.refetch}>{query.data?.length ? <div className="space-y-6">{query.data.map(post => <section key={post.id}><div className="flex items-center justify-between mb-3"><span>{post.is_published ? "منتشر شده" : "پیش‌نویس"}</span><Button variant="secondary" onClick={() => setEditing(post)}>ویرایش معرفی</Button></div><BookPostCard post={post} /></section>)}</div> : <EmptyState title="اولین معرفی کتاب را بنویسید" description="یک یا چند عکس اضافه کنید و از کتاب بگویید؛ می‌توانید پیش‌نویس را پیش از انتشار ذخیره کنید." />}</QueryBoundary>
  </div>;
}
function PostEditor({initial, onClose}) {
  const client = useQueryClient();
  const uploadInput = useRef(null);
  const [form,setForm]=useState(initial);
  const [uploads,setUploads]=useState([]);
  const [search,setSearch]=useState("");
  const [query,setQuery]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{const timer=setTimeout(()=>setQuery(search),250);return()=>clearTimeout(timer);},[search]);
  const books=useQuery({queryKey:["post-book-search",query],enabled:query.trim().length>0,queryFn:()=>apiClient.get("/catalog/search/",{params:{q:query}}).then(r=>r.data.results)});
  const invalidate=()=>{client.invalidateQueries({queryKey:["admin","posts"]});client.invalidateQueries({queryKey:["book-posts"]});onClose();};
  const save=useMutation({mutationFn:published=>{
    const data=new FormData();for(const key of ["title","body"])data.append(key,form[key]);data.append("is_published",String(published));data.append("book_ids",JSON.stringify(form.books.map(b=>b.id)));data.append("keep_image_ids",JSON.stringify(form.images.map(i=>i.id)));uploads.forEach(file=>data.append("uploads",file));
    return initial.id ? apiClient.patch(`/catalog/admin/posts/${initial.id}/`,data) : apiClient.post("/catalog/admin/posts/",data);
  },onSuccess:invalidate,onError:e=>setError(apiErrorMessage(e))});
  const remove=useMutation({mutationFn:()=>apiClient.delete(`/catalog/admin/posts/${initial.id}/`),onSuccess:invalidate,onError:e=>setError(apiErrorMessage(e))});
  const field=key=>({value:form[key],onChange:e=>setForm({...form,[key]:e.target.value})});
  const submit=published=>{setError("");if(!form.title.trim()||!form.body.trim()){setError("عنوان و متن معرفی را تکمیل کنید.");return;}if(published && !form.images.length && !uploads.length){setError("برای انتشار، دست‌کم یک تصویر اضافه کنید.");return;}save.mutate(published);};
  return <form className="post-editor space-y-4" onSubmit={e=>{e.preventDefault();submit(form.is_published);}}>
    <h2 className="section-title">{initial.id ? "ویرایش معرفی" : "معرفی تازه"}</h2><Input label="عنوان معرفی" maxLength={200} required {...field("title")} /><Textarea label="متن معرفی" rows={7} required {...field("body")} />
    <label className="field"><span className="field-label">تصاویر معرفی</span><input ref={uploadInput} className="sr-only" tabIndex={-1} type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e=>{const files=Array.from(e.target.files);e.target.value="";if(files.some(f=>f.size>5*1024*1024)||files.length+uploads.length+form.images.length>10){setError("حداکثر ۱۰ تصویر، هرکدام تا ۵ مگابایت انتخاب کنید.");return;}setError("");setUploads([...uploads,...files]);}} /></label><Button variant="secondary" onClick={() => uploadInput.current.click()}>افزودن عکس‌ها</Button><p className="text-sm text-ink-500">حداکثر ۱۰ عکس؛ JPG، PNG یا WebP، هر عکس تا ۵ مگابایت. عکس اول، تصویر اصلی معرفی است.</p>
    <div className="post-thumbnails">{form.images.map((image,i)=><div key={image.id}><img src={image.image} alt={`تصویر ${toPersianDigits(i+1)}`} /><Button variant="ghost" onClick={()=>setForm({...form,images:form.images.filter(x=>x.id!==image.id)})}>حذف تصویر {toPersianDigits(i+1)}</Button></div>)}{uploads.map((file,i)=><div key={`${file.name}-${i}`}><UploadPreview file={file} index={i} /><Button variant="ghost" onClick={()=>setUploads(uploads.filter((_,j)=>j!==i))}>حذف عکس تازه {toPersianDigits(i+1)}</Button></div>)}</div>
    <Input label="افزودن لینک کتاب (اختیاری)" value={search} onChange={e=>setSearch(e.target.value)} />
    {query && <QueryBoundary isLoading={books.isLoading} isError={books.isError} onRetry={books.refetch}><div className="post-book-results">{books.data?.filter(b=>!form.books.some(x=>x.id===b.id)).map(book=><Button key={book.id} variant="secondary" onClick={()=>{setForm({...form,books:[...form.books,book]});setSearch("");setQuery("");}}>افزودن {toPersianDigits(book.title)}</Button>)}{!books.data?.length && <p>کتابی پیدا نشد.</p>}</div></QueryBoundary>}
    <div className="flex flex-wrap gap-2">{form.books.map(book=><Button key={book.id} variant="ghost" onClick={()=>setForm({...form,books:form.books.filter(b=>b.id!==book.id)})}>حذف لینک {toPersianDigits(book.title)}</Button>)}</div>
    {error && <p role="alert" className="field-error">{error}</p>}
    <div className="flex flex-wrap gap-2"><Button type="submit" disabled={save.isPending || remove.isPending}>{form.is_published ? "ذخیره تغییرات" : "ذخیره پیش‌نویس"}</Button><Button variant="secondary" disabled={save.isPending || remove.isPending} onClick={()=>submit(!form.is_published)}>{form.is_published ? "برداشتن از فروشگاه" : "انتشار در فروشگاه"}</Button><Button variant="ghost" onClick={onClose}>انصراف</Button>{initial.id && <Button variant="danger" disabled={save.isPending || remove.isPending} onClick={()=>{if(window.confirm("این معرفی و عکس‌هایش حذف شوند؟"))remove.mutate();}}>حذف معرفی</Button>}</div>
  </form>;
}

function UploadPreview({ file, index }) {
  const ref = useRef(null);
  useEffect(() => { const url = URL.createObjectURL(file); ref.current.src = url; return () => URL.revokeObjectURL(url); }, [file]);
  return <img ref={ref} alt={`تصویر تازه ${toPersianDigits(index + 1)}`} />;
}
