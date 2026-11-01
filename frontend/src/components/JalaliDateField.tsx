import { useEffect, useId, useMemo, useRef, useState } from "react";
import {
  MONTH_NAMES, WEEKDAY_NAMES, formatJalaliSafe, fromGregorian, gToIso, isoToG,
  jalaliNow, monthLength, parseJalali, saturdayIndex, shiftJalaliMonth, toGregorian, todayIso,
} from "../lib/jalali";
import { useFieldAttrs } from "./ui";

type Props = {
  value: string;
  onChange: (iso: string) => void;
  label?: string;
  disabled?: boolean;
  /** کمینه‌ی تاریخ مجاز (ISO میلادی)؛ روزهای قبل از آن غیرفعال می‌شوند */
  min?: string;
  /** بیشینه‌ی تاریخ مجاز (ISO میلادی) */
  max?: string;
};

type View = { jy: number; jm: number };

function viewOf(iso: string): View {
  try {
    const j = iso ? fromGregorian(isoToG(iso)) : jalaliNow();
    return { jy: j.jy, jm: j.jm };
  } catch {
    const j = jalaliNow();
    return { jy: j.jy, jm: j.jm };
  }
}

function tryParse(text: string): string | null {
  try {
    return parseJalali(text);
  } catch {
    return null;
  }
}

export function JalaliDateField({ value, onChange, label, disabled, min, max }: Props) {
  const attrs = useFieldAttrs();
  const popId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(() => (value ? formatJalaliSafe(value, false, "") : ""));
  const [view, setView] = useState<View>(() => viewOf(value));
  const [formatError, setFormatError] = useState("");
  const today = todayIso();

  // همگام‌سازی متن با مقدار فقط وقتی مقدار از بیرون تغییر کرده (نه هنگام تایپ کاربر)
  useEffect(() => {
    if (tryParse(text) !== value) setText(value ? formatJalaliSafe(value, false, "") : "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // بستن با کلیک بیرون از کنترل
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (rootRef.current && e.target instanceof Node && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
    };
  }, [open]);

  const cells = useMemo(() => {
    const out: { iso: string; jd: number }[] = [];
    let first: string;
    try {
      first = gToIso(toGregorian(view.jy, view.jm, 1));
    } catch {
      return out;
    }
    const pad = saturdayIndex(first);
    const ml = monthLength(view.jy, view.jm);
    for (let i = 0; i < pad; i++) out.push({ iso: "", jd: 0 });
    for (let jd = 1; jd <= ml; jd++) out.push({ iso: gToIso(toGregorian(view.jy, view.jm, jd)), jd });
    return out;
  }, [view]);

  const openPopover = () => {
    if (disabled) return;
    setView(viewOf(value));
    setOpen(true);
  };

  const commit = (iso: string) => {
    onChange(iso);
    setText(formatJalaliSafe(iso, false, ""));
    setFormatError("");
    setOpen(false);
    inputRef.current?.focus();
  };

  const move = (delta: number) => {
    const next = shiftJalaliMonth(view, delta);
    if (next) setView(next);
  };
  const canMove = (delta: number) => shiftJalaliMonth(view, delta) !== null;

  const outOfRange = (iso: string) => (min !== undefined && min !== "" && iso < min) || (max !== undefined && max !== "" && iso > max);

  const invalid = !!formatError || attrs["aria-invalid"] === true;

  return (
    <div
      className="datepicker"
      ref={rootRef}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.stopPropagation();
          setOpen(false);
          inputRef.current?.focus();
        }
      }}
    >
      <div className="datepicker-input">
        <input
          {...attrs}
          ref={inputRef}
          dir="ltr"
          className="ltr-input"
          value={text}
          disabled={disabled}
          placeholder="1405/01/01"
          inputMode="numeric"
          autoComplete="off"
          aria-label={attrs.id ? undefined : (label ?? "تاریخ شمسی")}
          aria-invalid={invalid ? true : undefined}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={open ? popId : undefined}
          onChange={(e) => {
            const raw = e.target.value;
            setText(raw);
            if (!raw.trim()) {
              setFormatError("");
              onChange("");
              return;
            }
            const iso = tryParse(raw);
            if (iso) {
              setFormatError("");
              onChange(iso);
              setView(viewOf(iso));
            }
          }}
          onBlur={() => {
            if (!text.trim()) { setFormatError(""); return; }
            const iso = tryParse(text);
            if (iso) {
              setText(formatJalaliSafe(iso, false, ""));
              setFormatError("");
            } else {
              setFormatError("تاریخ را به‌صورت سال/ماه/روز (مثل 1405/07/01) وارد کنید");
            }
          }}
          onClick={openPopover}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" && !open) { e.preventDefault(); openPopover(); }
          }}
        />
        <button
          type="button"
          className="icon-btn datepicker-toggle"
          aria-label="باز کردن تقویم"
          aria-expanded={open}
          disabled={disabled}
          onClick={() => (open ? setOpen(false) : openPopover())}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <rect x="3" y="5" width="18" height="16" rx="3" />
            <path d="M3 10h18M8 3v4M16 3v4" />
          </svg>
        </button>
      </div>
      {formatError ? <div className="error datepicker-error" role="alert">{formatError}</div> : null}
      {open && !disabled && (
        <div className="card datepicker-pop" id={popId} role="dialog" aria-label="تقویم شمسی">
          <div className="datepicker-head">
            <div className="datepicker-nav">
              <button type="button" className="btn ghost sm" aria-label="سال قبل" disabled={!canMove(-12)} onClick={() => move(-12)}>«</button>
              <button type="button" className="btn ghost sm" aria-label="ماه قبل" disabled={!canMove(-1)} onClick={() => move(-1)}>‹</button>
            </div>
            <strong aria-live="polite">{MONTH_NAMES[view.jm - 1]} {view.jy}</strong>
            <div className="datepicker-nav">
              <button type="button" className="btn ghost sm" aria-label="ماه بعد" disabled={!canMove(1)} onClick={() => move(1)}>›</button>
              <button type="button" className="btn ghost sm" aria-label="سال بعد" disabled={!canMove(12)} onClick={() => move(12)}>»</button>
            </div>
          </div>
          <div className="cal-grid datepicker-grid">
            {WEEKDAY_NAMES.map((w) => <div key={w} className="cal-head" title={w}>{w.slice(0, 1)}</div>)}
            {cells.map((c, i) => {
              if (!c.jd) return <span key={i} aria-hidden="true" />;
              const selected = c.iso === value;
              const disabledDay = outOfRange(c.iso);
              return (
                <button
                  key={i}
                  type="button"
                  className={`cal-cell day${selected ? " selected" : ""}${c.iso === today ? " today" : ""}`}
                  disabled={disabledDay}
                  aria-pressed={selected}
                  aria-current={c.iso === today ? "date" : undefined}
                  aria-label={`${c.jd} ${MONTH_NAMES[view.jm - 1]} ${view.jy}`}
                  onClick={() => commit(c.iso)}
                >
                  {c.jd}
                </button>
              );
            })}
          </div>
          <div className="datepicker-foot">
            <button type="button" className="btn ghost sm" disabled={outOfRange(today)} onClick={() => commit(today)}>امروز</button>
            <button type="button" className="btn ghost sm" onClick={() => setOpen(false)}>بستن</button>
          </div>
        </div>
      )}
    </div>
  );
}
