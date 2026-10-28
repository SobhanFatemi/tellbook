import { ButtonLink } from "../components/Button";
import { useStoreSettings } from "../hooks/useStoreSettings";
import Logo from "../components/Logo";
export default function Footer() {
  const { data: store } = useStoreSettings();
  return <footer className="site-footer"><div className="site-container footer-content">
    <div><Logo /><p className="mt-2 text-sm text-ink-400">کتاب دلخواهت را پیدا کن، یا تهیه‌اش را به ما بسپار.</p></div>
    <div className="flex flex-wrap gap-2"><ButtonLink variant="ghost" to="/search">فهرست کتاب‌ها</ButtonLink><ButtonLink variant="ghost" to="/request-a-book">درخواست کتاب</ButtonLink></div>
    <div className="flex flex-wrap gap-3">{store?.support_telegram && <a className="social-link" href={`https://t.me/${store.support_telegram}`} target="_blank" rel="noreferrer">پشتیبانی</a>}<a className="social-link" href="https://instagram.com/tellbooks.ir" target="_blank" rel="noreferrer"><img src="/brand/instagram.svg" alt="" width="18" height="18" />اینستاگرام</a><a className="social-link" href="https://t.me/tellbooks1" target="_blank" rel="noreferrer"><img src="/brand/telegram.svg" alt="" width="18" height="18" />تلگرام</a></div>
  </div></footer>;
}
