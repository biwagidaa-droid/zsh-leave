import {
  createContext, useContext, useEffect, useId, useRef,
  type ButtonHTMLAttributes, type InputHTMLAttributes, type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from "react";
import { useDocumentTitle } from "../lib/hooks";
import { STATUS_LABEL, STATUS_TONE } from "../lib/roles";

/* ───────────────────────── دکمه و برچسب ───────────────────────── */

export function Button({
  variant = "primary", size, loading, className, disabled, type = "button", children, ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "sm";
  /** در حال انجام عملیات: دکمه غیرفعال و چرخنده نمایش داده می‌شود */
  loading?: boolean;
}) {
  const cls = ["btn", variant !== "primary" ? variant : "", size === "sm" ? "sm" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <button {...props} type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined}>
      {loading ? <span className="spinner" aria-hidden="true" /> : null}
      {children}
    </button>
  );
}

export function Badge({ tone = "muted", children }: { tone?: "ok" | "warn" | "danger" | "info" | "accent" | "muted"; children: ReactNode }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "muted"}>{STATUS_LABEL[status] ?? status}</Badge>;
}

/* ───────────────────────── کارت و سرصفحه ───────────────────────── */

export function Card({ title, children, actions }: { title?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="card-head">
          {title ? <h2>{title}</h2> : <span />}
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  useDocumentTitle(title);
  return (
    <header className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div className="toolbar head-actions">{actions}</div> : null}
    </header>
  );
}

/* ───────────────────────── فیلد فرم (برچسب ↔ کنترل) ───────────────────────── */

type FieldCtx = { id: string; describedBy?: string; invalid: boolean; required: boolean };
const FieldContext = createContext<FieldCtx | null>(null);

/** ویژگی‌های دسترس‌پذیری که Field به کنترل داخلش می‌دهد (id، aria-describedby، aria-invalid). */
export type FieldAttrs = {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
  "aria-required"?: true;
};

export function useFieldAttrs(): FieldAttrs {
  const f = useContext(FieldContext);
  if (!f) return {};
  return {
    id: f.id,
    "aria-describedby": f.describedBy,
    "aria-invalid": f.invalid ? true : undefined,
    "aria-required": f.required ? true : undefined,
  };
}

export function Field({
  label, hint, error, required, children,
}: { label: string; hint?: string; error?: string; required?: boolean; children: ReactNode }) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = error ? errId : hint ? hintId : undefined;
  return (
    <div className={`field${error ? " invalid" : ""}`}>
      <label htmlFor={id}>
        {label}
        {required ? <span className="req" aria-hidden="true"> *</span> : null}
      </label>
      <FieldContext.Provider value={{ id, describedBy, invalid: !!error, required: !!required }}>
        <div className="control">{children}</div>
      </FieldContext.Provider>
      {hint && !error ? <div className="hint" id={hintId}>{hint}</div> : null}
      {error ? <div className="error" id={errId} role="alert">{error}</div> : null}
    </div>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  const attrs = useFieldAttrs();
  return <input {...attrs} {...props} />;
}
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  const attrs = useFieldAttrs();
  return <select {...attrs} {...props} />;
}
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const attrs = useFieldAttrs();
  return <textarea {...attrs} {...props} />;
}

export function Checkbox({
  label, hint, ...props
}: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { label: ReactNode; hint?: string }) {
  const id = useId();
  return (
    <div className="check">
      <input {...props} type="checkbox" id={props.id ?? id} />
      <label htmlFor={props.id ?? id}>
        {label}
        {hint ? <span className="hint">{hint}</span> : null}
      </label>
    </div>
  );
}

export function SearchInput(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & { "aria-label": string }) {
  return <input {...props} type="search" className={`search ${props.className ?? ""}`.trim()} autoComplete="off" />;
}

/* ───────────────────────── وضعیت‌های بارگذاری / خالی / خطا ───────────────────────── */

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

export function LoadingBlock({ label = "در حال بارگذاری…" }: { label?: string }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {hint ? <div>{hint}</div> : null}
    </div>
  );
}

export function Banner({ children, tone = "warn" }: { children: ReactNode; tone?: "warn" | "info" | "danger" }) {
  return (
    <div className={`banner ${tone === "warn" ? "" : tone}`.trim()} role={tone === "danger" ? "alert" : "status"}>
      {children}
    </div>
  );
}

/** پیام خطای بارگذاری با دکمه‌ی «تلاش دوباره». */
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="banner danger error-state" role="alert">
      <span>{message}</span>
      {onRetry ? <Button variant="secondary" size="sm" onClick={onRetry}>تلاش دوباره</Button> : null}
    </div>
  );
}

/* ───────────────────────── تب‌ها ───────────────────────── */

export function Tabs({
  value, onChange, items, label,
}: { value: string; onChange: (v: string) => void; items: { id: string; label: string }[]; label?: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    const n = items.length;
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const forward = rtl ? "ArrowLeft" : "ArrowRight";
    const backward = rtl ? "ArrowRight" : "ArrowLeft";
    let next = index;
    if (e.key === forward) next = (index + 1) % n;
    else if (e.key === backward) next = (index - 1 + n) % n;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = n - 1;
    else return;
    e.preventDefault();
    onChange(items[next].id);
    refs.current[next]?.focus();
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((it, i) => (
        <button
          key={it.id}
          ref={(el) => { refs.current[i] = el; }}
          type="button"
          role="tab"
          aria-selected={value === it.id}
          tabIndex={value === it.id ? 0 : -1}
          onKeyDown={(e) => onKey(e, i)}
          onClick={() => onChange(it.id)}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

/** انتخاب یکی از چند گزینه‌ی کوتاه (مثلاً روزانه/ساعتی)؛ معنایی radiogroup با پیمایش کیبورد. */
export function Segmented({
  value, onChange, items, label,
}: { value: string; onChange: (v: string) => void; items: { id: string; label: string; disabled?: boolean }[]; label: string }) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
    const enabled = items.map((it, i) => (it.disabled ? -1 : i)).filter((i) => i >= 0);
    if (!enabled.length) return;
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const forward = rtl ? "ArrowLeft" : "ArrowRight";
    const backward = rtl ? "ArrowRight" : "ArrowLeft";
    const pos = enabled.indexOf(index);
    let next = -1;
    if (e.key === forward || e.key === "ArrowDown") next = enabled[(pos + 1) % enabled.length];
    else if (e.key === backward || e.key === "ArrowUp") next = enabled[(pos - 1 + enabled.length) % enabled.length];
    else return;
    e.preventDefault();
    onChange(items[next].id);
    refs.current[next]?.focus();
  };
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {items.map((it, i) => (
        <button
          key={it.id}
          ref={(el) => { refs.current[i] = el; }}
          type="button"
          role="radio"
          aria-checked={value === it.id}
          tabIndex={value === it.id ? 0 : -1}
          disabled={it.disabled}
          onKeyDown={(e) => onKey(e, i)}
          onClick={() => onChange(it.id)}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

/* ───────────────────────── مودال و تأیید ───────────────────────── */

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    const node = dialogRef.current;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusables = (): HTMLElement[] =>
      node ? Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.getClientRects().length > 0) : [];

    const initial = node?.querySelector<HTMLElement>("[data-autofocus]")
      ?? focusables().find((el) => !el.classList.contains("modal-close"));
    (initial ?? node)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (!items.length) { e.preventDefault(); return; }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === node)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      if (previous && document.contains(previous)) previous.focus();
    };
  }, []);

  return (
    <div
      className="modal-back"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={dialogRef} tabIndex={-1}>
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="icon-btn modal-close" aria-label="بستن" onClick={onClose}>×</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title, message, confirmLabel = "تأیید", cancelLabel = "انصراف", danger, busy, onConfirm, onCancel,
}: {
  title: string; message: ReactNode; confirmLabel?: string; cancelLabel?: string;
  danger?: boolean; busy?: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  return (
    <Modal title={title} onClose={onCancel}>
      <div className="modal-body">{message}</div>
      <div className="toolbar modal-actions">
        <Button variant={danger ? "danger" : "primary"} loading={busy} onClick={onConfirm} data-autofocus>{confirmLabel}</Button>
        <Button variant="secondary" disabled={busy} onClick={onCancel}>{cancelLabel}</Button>
      </div>
    </Modal>
  );
}

/* ───────────────────────── آمار، نوار پیشرفت، صفحه‌بندی ───────────────────────── */

export function Stat({ label, value, hint, loading }: { label: string; value: string; hint?: string; loading?: boolean }) {
  return (
    <article className="card stat" aria-busy={loading || undefined}>
      <div className="hint">{label}</div>
      <div className="value">{loading ? "…" : value}</div>
      {hint ? <div className="hint">{hint}</div> : null}
    </article>
  );
}

export function Meter({
  value, max, label, tone = "primary",
}: { value: number; max: number; label: string; tone?: "primary" | "warn" | "danger" | "ok" }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div className="meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={value}>
      <div className={`meter-fill ${tone}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Pagination({
  page, pageSize, count, onChange,
}: { page: number; pageSize: number; count: number; onChange: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(count / Math.max(1, pageSize)));
  if (pages <= 1) return null;
  return (
    <nav className="pager" aria-label="صفحه‌بندی">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>قبلی</Button>
      <span aria-live="polite">صفحه {page} از {pages} · {count} مورد</span>
      <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>بعدی</Button>
    </nav>
  );
}

/** فهرست «برچسب: مقدار»؛ موارد خالی نمایش داده نمی‌شوند. */
export function DetailList({ items }: { items: { label: string; value: ReactNode }[] }) {
  const visible = items.filter((it) => it.value !== null && it.value !== undefined && it.value !== false && it.value !== "");
  return (
    <dl className="detail-list">
      {visible.map((it) => (
        <div key={it.label}>
          <dt>{it.label}</dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ───────────────────────── جدول داده (ریسپانسیو، با data-label برای موبایل) ───────────────────────── */

export type Column<T> = {
  key: string;
  label: string;
  render?: (row: T) => ReactNode;
  /** برای اعداد/کدها: چینش چپ‌به‌راست */
  ltr?: boolean;
};

export function DataTable<T>({
  columns, rows, rowKey, caption, empty,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption?: string;
  empty?: ReactNode;
}) {
  if (!rows.length) return <>{empty ?? <Empty title="موردی برای نمایش نیست" />}</>;
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label={caption ?? "جدول داده"}>
      <table className="data">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead>
          <tr>{columns.map((c) => <th key={c.key} scope="col">{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((c) => (
                <td key={c.key} data-label={c.label} className={c.ltr ? "ltr" : undefined}>
                  {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
