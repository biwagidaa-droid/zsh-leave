import { useCallback, useEffect, useRef, useState } from "react";
import { asApiError } from "../api/errors";

/**
 * بارگذاری ناهمگام با محافظت در برابر پاسخ‌های قدیمی (race) و به‌روزرسانی پس از unmount.
 * همیشه آخرین نسخه‌ی fn اجرا می‌شود؛ deps فقط تعیین می‌کند چه زمانی دوباره بارگذاری شود.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const reload = useCallback(async () => {
    const id = ++seq.current;
    const live = () => mounted.current && id === seq.current;
    setLoading(true);
    try {
      const value = await fnRef.current();
      if (!live()) return;
      setData(value);
      setError(null);
    } catch (e) {
      if (!live()) return;
      setError(asApiError(e).message);
      setData(null);
    } finally {
      if (live()) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { void reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}
