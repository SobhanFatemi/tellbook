import { Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import Header from "./Header";
import Footer from "./Footer";
export default function BuyerLayout() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  const wide = pathname === "/" || pathname === "/search" || pathname.startsWith("/books/");
  return <div className="buyer-shell"><Header /><main id="main-content" className={`site-container page-content ${wide ? "" : "page-content--account"}`}><Outlet /></main><Footer /></div>;
}
