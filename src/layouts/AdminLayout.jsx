import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Library, Building2, FileSpreadsheet, BookOpen, Images, LayoutDashboard, ClipboardList, ShoppingBag, Undo2, Truck, Tag, Settings, LogOut, Store, Menu, X, ChevronDown } from "lucide-react";
import Button, { ButtonLink } from "../components/Button";
import { useAuth } from "../hooks/useAuth";
import { toPersianDigits } from "../utils/persianFormat";
import { ACTIVITY_SECTIONS, useAdminActivity } from "../hooks/useAdminActivity";
const NAV_GROUPS = [
  { label: "پیگیری روزانه", items: [
    ["/admin/requests", ClipboardList, "درخواست‌های کتاب"], ["/admin/orders", ShoppingBag, "سفارش‌ها و پرداخت"],
    ["/admin/shipments", Truck, "مدیریت ارسال"], ["/admin/refunds", Undo2, "بازگشت وجه"],
    ["/admin/books/review", BookOpen, "بازبینی کتاب‌ها"], ["/admin/prices", Tag, "بازبینی قیمت‌ها"],
  ] },
  { label: "فهرست و محتوا", items: [
    ["/admin/books", Library, "کتاب‌ها و نسخه‌ها"], ["/admin/products", ShoppingBag, "محصولات و پک‌ها"],
    ["/admin/publishers", Building2, "ناشران"], ["/admin/imports", FileSpreadsheet, "فایل‌های اکسل"], ["/admin/posts", Images, "معرفی کتاب"],
  ] },
  { label: "تنظیمات فروش", items: [["/admin/discounts", Tag, "کدهای تخفیف"], ["/admin/settings", Settings, "تنظیمات فروشگاه"]] },
];
const MOBILE_LABELS = {
  "/admin/requests": "درخواست‌ها", "/admin/orders": "سفارش‌ها", "/admin/shipments": "ارسال‌ها",
  "/admin/books": "کتاب‌ها و نسخه‌ها", "/admin/products": "محصولات و پک‌ها", "/admin/imports": "فایل‌های اکسل",
};
const NAV_ITEMS = [["/admin", LayoutDashboard, "نمای کلی"], ...NAV_GROUPS.flatMap(group => group.items)];
export default function AdminLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const counts = useAdminActivity(user?.id, location.pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const title = NAV_ITEMS.find(([path]) => path === location.pathname)?.[2] || "مدیریت فروشگاه";
  function renderLink([to, Icon, label]) {
    const count = counts[ACTIVITY_SECTIONS[to]?.[0]] || 0;
    return <NavLink key={to} to={to} onClick={() => setMenuOpen(false)} end={to === "/admin" || to === "/admin/books"} className={({ isActive }) => `admin-nav-item${isActive || (to === "/admin/books" && /^\/admin\/books\/\d+/.test(location.pathname)) ? " is-active" : ""}`}><Icon size={19} aria-hidden="true" /><span className="admin-nav-caption"><span className="admin-nav-label"><span className="admin-nav-desktop-label">{label}</span><span className="admin-nav-mobile-label">{MOBILE_LABELS[to] || label}</span></span>{count > 0 && <span className="admin-unread-badge" aria-label={`${toPersianDigits(count)} به‌روزرسانی دیده‌نشده`}>{toPersianDigits(count)}</span>}</span></NavLink>;
  }
  return <div className="admin-shell">
    <a className="skip-link" href="#main-content">رفتن به محتوای صفحه</a>
    <aside className="admin-sidebar">
      <div className="admin-brand"><img src="/brand/tellbook-admin-wordmark.png" alt="مدیریت تلبوک" className="admin-wordmark" /></div>
      <button className="admin-menu-toggle" aria-label={menuOpen ? "بستن منوی مدیریت" : "باز کردن منوی مدیریت"} aria-expanded={menuOpen} aria-controls="admin-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={19} aria-hidden="true" /> : <Menu size={19} aria-hidden="true" />}<span>منوی مدیریت</span><ChevronDown size={16} className="admin-menu-chevron" aria-hidden="true" /></button>
      <nav id="admin-navigation" className={menuOpen ? "is-open" : ""} aria-label="منوی مدیریت">
        {renderLink(NAV_ITEMS[0])}
        {NAV_GROUPS.map(group => <section className="admin-nav-group" key={group.label} aria-label={group.label}><h2>{group.label}</h2><div className="admin-nav-group-links">{group.items.map(renderLink)}</div></section>)}
      </nav>
      <div className="admin-sidebar-footer"><ButtonLink to="/" variant="ghost"><Store size={18} />مشاهده فروشگاه</ButtonLink><Button variant="ghost" onClick={logout}><LogOut size={18} />خروج از حساب</Button></div>
    </aside>
    <div className="admin-workspace">
      <header className="admin-topbar"><span>{title}</span><div className="flex flex-wrap items-center gap-3"><span className="text-sm text-ink-400" dir="ltr">{toPersianDigits(user?.phone)}</span></div></header>
      <main id="main-content" className="admin-content"><Outlet /></main>
    </div>
  </div>;
}
