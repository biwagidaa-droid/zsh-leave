import { useId, useMemo, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";
import { Empty, ErrorState } from "./ui";

/* نمودارهای SVG داخلی (بدون وابستگی تازه): دایره‌ای، حلقه‌ای و ستونی.
   رنگ‌ها از متغیرهای --chart-N در tokens.css می‌آیند و با پوسته تیره عوض می‌شوند. */

export type ChartDatum = {
  label: string;
  value: number;
  /** رنگ دلخواه؛ در غیر این صورت از پالت استاندارد به ترتیب انتخاب می‌شود */
  color?: string;
  /** توضیح اضافه در Tooltip */
  hint?: string;
};

export type ChartStateProps = {
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyHint?: string;
};

const PALETTE_SIZE = 8;
export function chartColor(index: number): string {
  return `var(--chart-${(index % PALETTE_SIZE) + 1})`;
}

export function formatValue(v: number): string {
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
}

export function formatPercent(p: number): string {
  return `${Math.round(p * 10) / 10}٪`;
}

/* ───────────────────────── محاسبات خالص (قابل تست) ───────────────────────── */

export type Slice = { index: number; label: string; value: number; percent: number; start: number; end: number; mid: number };

/** زاویه‌ی هر قطعه بر حسب رادیان از بالای دایره، ساعت‌گرد. مقادیر منفی/نامعتبر صفر حساب می‌شوند. */
export function computeSlices(data: ChartDatum[]): { slices: Slice[]; total: number } {
  const safe = data.map((d) => (Number.isFinite(d.value) && d.value > 0 ? d.value : 0));
  const total = safe.reduce((a, b) => a + b, 0);
  const slices: Slice[] = [];
  let angle = 0;
  data.forEach((d, index) => {
    const v = safe[index];
    const frac = total > 0 ? v / total : 0;
    const start = angle;
    const end = angle + frac * Math.PI * 2;
    angle = end;
    slices.push({ index, label: d.label, value: v, percent: frac * 100, start, end, mid: (start + end) / 2 });
  });
  return { slices, total };
}

function pt(cx: number, cy: number, r: number, a: number): [number, number] {
  return [cx + r * Math.sin(a), cy - r * Math.cos(a)];
}

/** مسیر SVG یک قطعه؛ r=0 یعنی دایره‌ای (نه حلقه‌ای). قطعه‌ی ۱۰۰٪ به دو کمان شکسته می‌شود. */
export function slicePath(cx: number, cy: number, R: number, r: number, start: number, end: number): string {
  const sweep = end - start;
  if (sweep <= 0) return "";
  const f = (n: number) => n.toFixed(3);
  if (sweep >= Math.PI * 2 - 1e-6) {
    const mid = start + Math.PI;
    const [x1, y1] = pt(cx, cy, R, start);
    const [x2, y2] = pt(cx, cy, R, mid);
    const outer = `M${f(x1)} ${f(y1)} A${R} ${R} 0 1 1 ${f(x2)} ${f(y2)} A${R} ${R} 0 1 1 ${f(x1)} ${f(y1)}`;
    if (r <= 0) return `${outer} Z`;
    const [i1, j1] = pt(cx, cy, r, start);
    const [i2, j2] = pt(cx, cy, r, mid);
    return `${outer} M${f(i1)} ${f(j1)} A${r} ${r} 0 1 0 ${f(i2)} ${f(j2)} A${r} ${r} 0 1 0 ${f(i1)} ${f(j1)} Z`;
  }
  const large = sweep > Math.PI ? 1 : 0;
  const [ox1, oy1] = pt(cx, cy, R, start);
  const [ox2, oy2] = pt(cx, cy, R, end);
  if (r <= 0) return `M${cx} ${cy} L${f(ox1)} ${f(oy1)} A${R} ${R} 0 ${large} 1 ${f(ox2)} ${f(oy2)} Z`;
  const [ix1, iy1] = pt(cx, cy, r, start);
  const [ix2, iy2] = pt(cx, cy, r, end);
  return `M${f(ox1)} ${f(oy1)} A${R} ${R} 0 ${large} 1 ${f(ox2)} ${f(oy2)} L${f(ix2)} ${f(iy2)} A${r} ${r} 0 ${large} 0 ${f(ix1)} ${f(iy1)} Z`;
}

/** سقف «زیبا» برای محور عمودی ستونی (۱، ۲، ۵ × توان ده). */
export function niceMax(max: number): number {
  if (!Number.isFinite(max) || max <= 0) return 1;
  const exp = Math.floor(Math.log10(max));
  const base = 10 ** exp;
  const f = max / base;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
  return nice * base;
}

/* ───────────────────────── Tooltip مشترک ───────────────────────── */

type Tip = { x: number; y: number; title: string; lines: string[] } | null;

function useTooltip() {
  const wrap = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<Tip>(null);
  const showAt = (clientX: number, clientY: number, title: string, lines: string[]) => {
    const r = wrap.current?.getBoundingClientRect();
    if (!r) return;
    setTip({ x: clientX - r.left, y: clientY - r.top, title, lines });
  };
  const showForElement = (el: Element, title: string, lines: string[]) => {
    const r = el.getBoundingClientRect();
    showAt(r.left + r.width / 2, r.top + r.height / 2, title, lines);
  };
  const hide = () => setTip(null);
  const node = tip ? (
    <div className="chart-tip" role="status" style={{ left: tip.x, top: tip.y }}>
      <strong>{tip.title}</strong>
      {tip.lines.map((l) => <div key={l}>{l}</div>)}
    </div>
  ) : null;
  return { wrap, showAt, showForElement, hide, node };
}

function ChartSkeleton({ kind }: { kind: "round" | "bars" }) {
  return (
    <div className={`chart-skeleton ${kind}`} role="status" aria-busy="true" aria-label="در حال بارگذاری نمودار">
      {kind === "round" ? <span className="sk-circle" /> : <span className="sk-bars"><i /><i /><i /><i /><i /></span>}
      <span className="sr-only">در حال بارگذاری نمودار…</span>
    </div>
  );
}

function pre(state: ChartStateProps, kind: "round" | "bars", data: ChartDatum[]): JSX.Element | null {
  if (state.loading) return <ChartSkeleton kind={kind} />;
  if (state.error) return <ErrorState message={state.error} onRetry={state.onRetry} />;
  if (!data.length || data.every((d) => !(d.value > 0))) {
    return <Empty title={state.emptyTitle ?? "داده‌ای برای نمایش نیست"} hint={state.emptyHint} />;
  }
  return null;
}

/* ───────────────────────── دایره‌ای و حلقه‌ای ───────────────────────── */

export function DonutChart({
  data, title, variant = "donut", totalLabel = "مجموع", ...state
}: { data: ChartDatum[]; title: string; variant?: "donut" | "pie"; totalLabel?: string } & ChartStateProps) {
  const uid = useId();
  const tooltip = useTooltip();
  const [active, setActive] = useState<number | null>(null);
  const { slices, total } = useMemo(() => computeSlices(data), [data]);
  const blocked = pre(state, "round", data);
  if (blocked) return blocked;

  const CX = 100; const CY = 100; const R = 88; const r = variant === "donut" ? 54 : 0;
  const colorOf = (i: number) => data[i].color ?? chartColor(i);
  const lines = (s: Slice) => [`${formatValue(s.value)} (${formatPercent(s.percent)} از کل)`, ...(data[s.index].hint ? [data[s.index].hint as string] : [])];
  const onMove = (e: ReactPointerEvent, s: Slice) => { setActive(s.index); tooltip.showAt(e.clientX, e.clientY, s.label, lines(s)); };
  const off = () => { setActive(null); tooltip.hide(); };
  const focused = active != null ? slices[active] : null;

  return (
    <figure className="chart" ref={tooltip.wrap} aria-labelledby={`${uid}-t`}>
      <figcaption id={`${uid}-t`} className="sr-only">{title}</figcaption>
      <div className="chart-body">
        <svg className="chart-svg" viewBox="0 0 200 200" role="img" aria-label={`${title}: ${slices.map((s) => `${s.label} ${formatValue(s.value)}`).join("، ")}`}>
          <g className="chart-shadow">
            {slices.map((s) => {
              if (s.value <= 0) return null;
              const dx = Math.sin(s.mid) * 5; const dy = -Math.cos(s.mid) * 5;
              const on = active === s.index;
              const style: CSSProperties = { transform: on ? `translate(${dx}px, ${dy}px)` : undefined, animationDelay: `${s.index * 70}ms` };
              return (
                <path
                  key={s.index}
                  className={`chart-slice${on ? " on" : ""}${active != null && !on ? " dim" : ""}`}
                  d={slicePath(CX, CY, R, r, s.start, s.end)}
                  fillRule="evenodd"
                  fill={colorOf(s.index)}
                  stroke="var(--bg-elev)"
                  strokeWidth="2"
                  style={style}
                  tabIndex={0}
                  role="img"
                  aria-label={`${s.label}: ${formatValue(s.value)}، ${formatPercent(s.percent)}`}
                  onPointerMove={(e) => onMove(e, s)}
                  onPointerLeave={off}
                  onFocus={(e) => { setActive(s.index); tooltip.showForElement(e.currentTarget, s.label, lines(s)); }}
                  onBlur={off}
                />
              );
            })}
          </g>
          {variant === "donut" && (
            <g className="chart-center" aria-hidden="true">
              <text x={CX} y={CY - 2} textAnchor="middle" className="chart-center-value">{formatValue(focused ? focused.value : total)}</text>
              <text x={CX} y={CY + 16} textAnchor="middle" className="chart-center-label">{focused ? formatPercent(focused.percent) : totalLabel}</text>
            </g>
          )}
        </svg>
        <ul className="chart-legend">
          {slices.map((s) => (
            <li
              key={s.index}
              className={active === s.index ? "on" : undefined}
              onPointerEnter={() => setActive(s.index)}
              onPointerLeave={() => setActive(null)}
            >
              <i style={{ background: colorOf(s.index) }} aria-hidden="true" />
              <span className="lbl">{s.label}</span>
              <span className="val">{formatValue(s.value)}</span>
              <span className="pct">{formatPercent(s.percent)}</span>
            </li>
          ))}
        </ul>
      </div>
      {tooltip.node}
    </figure>
  );
}

/* ───────────────────────── ستونی ───────────────────────── */

export function ColumnChart({
  data, title, valueLabel = "مقدار", ...state
}: { data: ChartDatum[]; title: string; valueLabel?: string } & ChartStateProps) {
  const uid = useId();
  const tooltip = useTooltip();
  const [active, setActive] = useState<number | null>(null);
  const blocked = pre(state, "bars", data);
  if (blocked) return blocked;

  const W = Math.max(320, data.length * 44 + 56); const H = 220;
  const padL = 40; const padR = 8; const padT = 12; const padB = 46;
  const ceiling = niceMax(Math.max(...data.map((d) => (d.value > 0 ? d.value : 0))));
  const plotW = W - padL - padR; const plotH = H - padT - padB;
  const slot = plotW / data.length; const bw = Math.min(30, slot * 0.62);
  const ticks = [0, 0.5, 1].map((f) => f * ceiling);
  const y = (v: number) => padT + plotH - (Math.max(0, v) / ceiling) * plotH;

  return (
    <figure className="chart" ref={tooltip.wrap} aria-labelledby={`${uid}-t`}>
      <figcaption id={`${uid}-t`} className="sr-only">{title}</figcaption>
      <div className="chart-scroll">
        <svg className="chart-svg wide" style={{ minWidth: W }} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${title}: ${data.map((d) => `${d.label} ${formatValue(d.value)}`).join("، ")}`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} className="chart-grid" />
              <text x={padL - 6} y={y(t) + 4} textAnchor="end" className="chart-axis">{formatValue(t)}</text>
            </g>
          ))}
          <g className="chart-shadow">
            {data.map((d, i) => {
              const h = Math.max(0, plotH - (y(d.value) - padT));
              const x = padL + slot * i + (slot - bw) / 2;
              const on = active === i;
              const lines = [`${valueLabel}: ${formatValue(d.value)}`, ...(d.hint ? [d.hint] : [])];
              return (
                <rect
                  key={i}
                  className={`chart-bar${on ? " on" : ""}${active != null && !on ? " dim" : ""}`}
                  x={x} y={padT + plotH - h} width={bw} height={h} rx={5}
                  fill={d.color ?? chartColor(0)}
                  style={{ animationDelay: `${i * 40}ms` }}
                  tabIndex={0}
                  role="img"
                  aria-label={`${d.label}: ${formatValue(d.value)}`}
                  onPointerMove={(e) => { setActive(i); tooltip.showAt(e.clientX, e.clientY, d.label, lines); }}
                  onPointerLeave={() => { setActive(null); tooltip.hide(); }}
                  onFocus={(e) => { setActive(i); tooltip.showForElement(e.currentTarget, d.label, lines); }}
                  onBlur={() => { setActive(null); tooltip.hide(); }}
                />
              );
            })}
          </g>
          {data.map((d, i) => (
            <text key={i} x={padL + slot * i + slot / 2} y={H - padB + 16} textAnchor="middle" className="chart-axis">{d.label}</text>
          ))}
        </svg>
      </div>
      {tooltip.node}
    </figure>
  );
}
