import Button from "./Button";
import { formatNumber, toPersianDigits } from "../utils/persianFormat";
export default function AdminPagination({ data, page, onChange }) {
  if (!data) return null;
  return <nav aria-label="صفحه‌بندی" className="admin-pagination"><span>{formatNumber(data.count)} مورد · صفحه {toPersianDigits(page)}</span><div className="flex gap-2"><Button variant="ghost" disabled={!data.previous} onClick={()=>onChange(page-1)}>صفحه قبل</Button><Button variant="ghost" disabled={!data.next} onClick={()=>onChange(page+1)}>صفحه بعد</Button></div></nav>;
}
