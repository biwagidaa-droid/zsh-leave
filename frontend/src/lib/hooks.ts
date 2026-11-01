import { useEffect, useState } from "react";
import { setPageTitle } from "./documentChrome";

/** مقدار را با تأخیر منتشر می‌کند؛ برای جستجو تا هر کلید یک درخواست نرود. */
export function useDebounced<T>(value: T, delay = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), delay);
    return () => window.clearTimeout(t);
  }, [value, delay]);
  return v;
}

/** عنوان تب مرورگر را برای هر صفحه تنظیم می‌کند؛ نشانگر اعلان نخوانده جداگانه اعمال می‌شود. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    setPageTitle(title);
  }, [title]);
}

/** نخستین کنترل نامعتبر داخل یک فرم را فوکوس می‌کند. */
export function focusFirstInvalid(root: HTMLElement | null): void {
  if (!root) return;
  window.setTimeout(() => {
    const el = root.querySelector<HTMLElement>('[aria-invalid="true"]');
    el?.focus();
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, 0);
}
