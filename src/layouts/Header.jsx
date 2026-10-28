import { useCart } from "../hooks/useCart";
import { formatNumber } from "../utils/persianFormat";
import { Link, NavLink, useNavigate, useLocation } from "react-router-dom";
import { Search, ShoppingBag, ClipboardList, MapPin, User, Truck, Library, LayoutDashboard, BookOpen, BookPlus, ChevronDown, LogIn, ShoppingBasket } from "lucide-react";
import { useState, useRef, useEffect, useId } from "react";
import { ButtonLink } from "../components/Button";
import Logo from "../components/Logo";
import { useAuth } from "../hooks/useAuth";

const accountLinks = [["/profile", User, "پروفایل"], ["/requests", ClipboardList, "درخواست‌های من"], ["/orders", ShoppingBag, "سفارش‌های من"], ["/shelf", Library, "قفسه من"], ["/shipments", Truck, "ارسال‌های من"], ["/addresses", MapPin, "آدرس‌های من"]];
export default function Header() {
  const cart = useCart();
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  return <header className="site-header">
    <a className="skip-link" href="#main-content">رفتن به محتوای صفحه</a>
    <div className="site-container header-main">
      <Link to="/" className="brand-link" aria-label="تلبوک؛ صفحه اصلی"><Logo size="lg" /></Link>
      <form role="search" className="site-search" onSubmit={e => { e.preventDefault(); navigate(`/search?q=${encodeURIComponent(query)}`); }}>
        <Search size={20} aria-hidden="true" />
        <input aria-label="جستجوی کتاب یا نویسنده" placeholder="عنوان کتاب یا نام نویسنده…" value={query} onChange={e => setQuery(e.target.value)} />
        <button type="submit">جستجو</button>
      </form>
      <div className="header-actions">
        <ButtonLink to="/cart" variant="ghost" className="header-cart"><ShoppingBasket size={19} aria-hidden="true" /><span>سبد خرید</span>{cart.count > 0 && <span className="account-cart-count">{formatNumber(cart.count)}</span>}</ButtonLink>
        <AccountDropdown />
      </div>
    </div>
    <nav aria-label="منوی فروشگاه" className="site-container store-navigation">
      <NavItem to="/search" icon={BookOpen}>فهرست کتاب‌ها</NavItem>
      <NavItem to="/products" icon={ShoppingBag}>پک‌ها و همراه‌های کتاب</NavItem>
      <NavItem to="/request-a-book" icon={BookPlus}>درخواست کتاب</NavItem>
    </nav>
  </header>;
}
function NavItem({ to, icon: Icon, children }) {
  return <NavLink to={to} className={({ isActive }) => `nav-item${isActive ? " is-active" : ""}`}><Icon size={17} aria-hidden="true" />{children}</NavLink>;
}

function AccountDropdown() {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();
  const [openedAt, setOpenedAt] = useState(null);
  const open = openedAt === location.key;
  const root = useRef(null);
  const trigger = useRef(null);
  const id = useId();
  const close = () => setOpenedAt(null);
  useEffect(() => {
    if (!open) return;
    const outside = event => { if (!root.current?.contains(event.target)) setOpenedAt(null); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  return <div className="header-account" ref={root}
    onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) close(); }}
    onKeyDown={event => { if (event.key === "Escape" && open) { event.preventDefault(); close(); trigger.current?.focus(); } }}>
    <button ref={trigger} type="button" className="button button--ghost account-trigger" aria-expanded={open} aria-controls={id} onClick={() => setOpenedAt(open ? null : location.key)}>
      <User size={18} aria-hidden="true" /><span>حساب من</span><ChevronDown size={16} aria-hidden="true" />
    </button>
    {open && <nav id={id} className="account-dropdown" aria-label="حساب من">
      {!isAuthenticated && <NavItem to="/login" icon={LogIn}>ورود / ثبت‌نام</NavItem>}
      {accountLinks.map(([to, icon, label]) => <div key={to} onClick={close}><NavItem to={to} icon={icon}>{label}</NavItem></div>)}
      {user?.role === "creator" && <div className="account-admin-link" onClick={close}><NavItem to="/admin" icon={LayoutDashboard}>مدیریت فروشگاه</NavItem></div>}
    </nav>}
  </div>;
}
