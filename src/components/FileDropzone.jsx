import { toPersianDigits } from "../utils/persianFormat";
import { useEffect, useId, useRef, useState } from "react";
import { ImagePlus, X } from "lucide-react";
import clsx from "clsx";

export default function FileDropzone({ label = "انتخاب تصویر", value, onChange, accept = "image/jpeg,image/png,image/webp", maxSizeMB = 5 }) {
  const inputRef = useRef(null);
  const id = useId();
  const [isDragging, setIsDragging] = useState(false);
  const previewRef = useRef(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!value) return;
    const url = URL.createObjectURL(value);
    if (previewRef.current) previewRef.current.src = url;
    return () => URL.revokeObjectURL(url);
  }, [value]);

  const handleFiles = (files) => {
    const file = files?.[0];
    if (!file) return;
    if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > maxSizeMB * 1024 * 1024) {
      setError(`تصویر JPG، PNG یا WebP با حجم حداکثر ${toPersianDigits(maxSizeMB)} مگابایت انتخاب کنید.`);
      return;
    }
    setError("");
    onChange(file);
  };

  return (
    <div>
      <span id={`${id}-label`} className="block mb-1.5 text-sm font-medium text-ink-600">{label}</span>
      {value ? (
        <div className="relative w-40 h-40 rounded-xl overflow-hidden border border-cream-300">
          <img ref={previewRef} alt={`پیش‌نمایش ${label}`} className="w-full h-full object-contain" />
          <button type="button" aria-label="حذف تصویر" onClick={() => onChange(null)}
            className="absolute top-1 end-1 bg-ink-700/90 text-white rounded-full w-11 h-11 flex items-center justify-center focus-visible:outline focus-visible:outline-2 focus-visible:outline-maroon-500">
            <X size={18} />
          </button>
        </div>
      ) : (
        <button type="button" aria-labelledby={`${id}-label`} aria-describedby={`${id}-hint`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => { e.preventDefault(); setIsDragging(false); handleFiles(e.dataTransfer.files); }}
          className={clsx("w-full min-h-36 rounded-xl border border-dashed flex flex-col items-center justify-center gap-2 p-4 text-ink-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-maroon-500", isDragging ? "border-maroon-500 bg-cream-100" : "border-cream-300 hover:border-dusty-500")}>
          <ImagePlus size={28} aria-hidden="true" />
          <span className="text-sm">انتخاب تصویر یا کشیدن فایل اینجا</span>
        </button>
      )}
      <p id={`${id}-hint`} className="text-xs text-ink-600 mt-2">JPG، PNG یا WebP، حداکثر {toPersianDigits(maxSizeMB)} مگابایت</p>
      <input ref={inputRef} type="file" accept={accept} aria-label={label} className="hidden"
        onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }} />
      {error && <p role="alert" className="text-sm text-red-600 mt-2">{error}</p>}
    </div>
  );
}
