import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

export type ToastTone = "info" | "success" | "danger";
type Toast = { id: number; text: string; tone: ToastTone };
type Push = (text: string, tone?: ToastTone) => void;

const Ctx = createContext<Push>(() => undefined);
const DURATION: Record<ToastTone, number> = { info: 3800, success: 3800, danger: 7000 };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const timers = useRef(new Map<number, number>());
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => {
    const t = timers.current.get(id);
    if (t !== undefined) window.clearTimeout(t);
    timers.current.delete(id);
    setItems((xs) => xs.filter((x) => x.id !== id));
  }, []);

  const push = useCallback<Push>((text, tone = "info") => {
    seq.current += 1;
    const id = seq.current;
    setItems((xs) => [...xs.slice(-3), { id, text, tone }]);
    timers.current.set(id, window.setTimeout(() => dismiss(id), DURATION[tone]));
  }, [dismiss]);

  useEffect(() => {
    const map = timers.current;
    return () => { map.forEach((t) => window.clearTimeout(t)); map.clear(); };
  }, []);

  const value = useMemo(() => push, [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-atomic="false">
        {items.map((t) => (
          <div
            key={t.id}
            className={`toast ${t.tone}`}
            role={t.tone === "danger" ? "alert" : "status"}
          >
            <span>{t.text}</span>
            <button type="button" className="toast-close" aria-label="بستن پیام" onClick={() => dismiss(t.id)}>×</button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): Push {
  return useContext(Ctx);
}
