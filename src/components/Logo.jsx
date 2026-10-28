import { useState } from "react";
import { useStoreSettings } from "../hooks/useStoreSettings";

const DEFAULT_LOGO = "/brand/tellbook-wordmark.png";

export default function Logo({ size = "md" }) {
  const { data } = useStoreSettings();
  const [failedUrls, setFailedUrls] = useState([]);
  const dimensions = { sm: "h-9 max-w-28", md: "h-12 max-w-40", lg: "h-20 max-w-64" };
  const source = data?.logo && !failedUrls.includes(data.logo) ? data.logo : DEFAULT_LOGO;
  if (failedUrls.includes(source)) return <span className="font-bold text-current whitespace-nowrap">تلبوک</span>;
  return <img src={source} alt="تلبوک" onError={() => setFailedUrls(urls => [...urls, source])}
    className={`${dimensions[size]} store-logo object-contain shrink-0`} />;
}
