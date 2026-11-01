import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, DEMO_MODE } from "../api";
import type { CalendarEvent } from "../api/types";
import { Button, Card, DataTable, Empty, ErrorState, LoadingBlock, Meter, PageHeader, Tabs, type Column } from "../components/ui";
import {
  MONTH_NAMES, WEEKDAY_NAMES, addDaysIso, formatJalaliSafe, gToIso, jalaliNow,
  monthLength, pythonWeekday, saturdayIndex, shiftJalaliMonth, toGregorian, todayIso,
} from "../lib/jalali";
import { hasAny } from "../lib/roles";
import { useAsync } from "../lib/useAsync";
import { useAuth } from "../state/Auth";

type Scope = "me" | "team" | "org";
const MAX_CHIPS = 3;

/** ساعت مرخصی ساعتی برای نمایش کنار برچسب رویداد تقویم؛ برای روزانه خالی است. */
function eventTime(e: CalendarEvent): string {
  return e.durationKind === "hourly" && e.startTime && e.endTime ? ` ${e.startTime}–${e.endTime}` : "";
}

function initialScope(roles: Parameters<typeof hasAny>[0]): Scope {
  if (DEMO_MODE && hasAny(roles, "hr", "exec")) return "org";
  if (hasAny(roles, "admin")) return "org";
  if (hasAny(roles, "manager")) return "team";
  return "me";
}

export function CalendarPage() {
  const { user } = useAuth();
  const roles = user?.roles ?? [];
  const now = jalaliNow();
  const [view, setView] = useState({ jy: now.jy, jm: now.jm });
  const [scope, setScope] = useState<Scope>(() => initialScope(roles));
  const ml = monthLength(view.jy, view.jm);
  const from = gToIso(toGregorian(view.jy, view.jm, 1));
  const to = gToIso(toGregorian(view.jy, view.jm, ml));
  const { data, error, loading, reload } = useAsync(() => api.calendar(from, to, scope), [from, to, scope]);
  const { data: holidays, error: holidaysError, loading: holidaysLoading, reload: reloadHolidays } =
    useAsync(() => api.calendarHolidays(from, to), [from, to]);
  const pad = saturdayIndex(from);
  const today = todayIso();

  const cells = useMemo(() => {
    const arr: { iso: string; jd: number }[] = [];
    for (let i = 0; i < pad; i++) arr.push({ iso: "", jd: 0 });
    for (let jd = 1; jd <= ml; jd++) arr.push({ iso: gToIso(toGregorian(view.jy, view.jm, jd)), jd });
    return arr;
  }, [pad, ml, view]);

  const eventsByDay = (iso: string): CalendarEvent[] => (data ?? []).filter((e) => e.start <= iso && e.end >= iso);
  const holidaysOn = (iso: string) =>
    (holidays ?? []).filter((holiday) => holiday.start <= iso && holiday.end >= iso);

  const go = (delta: number) => {
    const next = shiftJalaliMonth(view, delta);
    if (next) setView(next);
  };
  const isCurrent = view.jy === now.jy && view.jm === now.jm;

  const tabs: { id: Scope; label: string }[] = [
    { id: "me", label: "شخصی" },
    ...(DEMO_MODE
      ? (hasAny(roles, "manager", "hr", "exec") ? [{ id: "team" as const, label: "تیم" }] : [])
      : (hasAny(roles, "manager") ? [{ id: "team" as const, label: "تیم" }] : [])),
    ...((DEMO_MODE && hasAny(roles, "hr", "exec")) || hasAny(roles, "admin")
      ? [{ id: "org" as const, label: "سازمان" }]
      : []),
  ];
  // اگر نقش کاربر دامنه‌ی انتخاب‌شده را مجاز نمی‌داند، به «شخصی» برگرد
  const activeScope: Scope = tabs.some((t) => t.id === scope) ? scope : "me";

  return (
    <>
      <PageHeader
        title="تقویم شمسی"
        subtitle="همکاران نوع را نمی‌بینند مگر تنظیم حریم خصوصی اجازه دهد"
        actions={(
          <>
            <Button variant="secondary" size="sm" disabled={!shiftJalaliMonth(view, -1)} onClick={() => go(-1)}>ماه قبل</Button>
            <strong aria-live="polite">{MONTH_NAMES[view.jm - 1]} {view.jy}</strong>
            <Button variant="secondary" size="sm" disabled={!shiftJalaliMonth(view, 1)} onClick={() => go(1)}>ماه بعد</Button>
            <Button variant="ghost" size="sm" disabled={isCurrent} onClick={() => setView({ jy: now.jy, jm: now.jm })}>امروز</Button>
          </>
        )}
      />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      {holidaysError && <ErrorState message={holidaysError} onRetry={() => void reloadHolidays()} />}
      <Tabs value={activeScope} onChange={(v) => setScope(v as Scope)} items={tabs} label="دامنه تقویم" />
      {(loading && !data) || (holidaysLoading && !holidays) ? <LoadingBlock /> : null}
      <div className="cal-grid" aria-busy={loading}>
        {WEEKDAY_NAMES.map((w) => (
          <div key={w} className="cal-head">
            <span className="full">{w}</span>
            <span className="short" aria-hidden="true">{w.slice(0, 1)}</span>
          </div>
        ))}
        {cells.map((c, i) => {
          if (!c.jd) return <div key={i} className="cal-cell off" aria-hidden="true" />;
          const evs = eventsByDay(c.iso);
          const hol = holidaysOn(c.iso);
          const friday = (i % 7) === 6;
          const cls = ["cal-cell", friday ? "weekend" : "", hol.length ? "holiday" : "", c.iso === today ? "today" : ""].filter(Boolean).join(" ");
          const label = `${c.jd} ${MONTH_NAMES[view.jm - 1]}${hol.length ? `، تعطیل: ${hol.map((h) => h.title).join("، ")}` : ""}${evs.length ? `، ${evs.length} غیبت` : ""}`;
          return (
            <div key={i} className={cls} aria-current={c.iso === today ? "date" : undefined}>
              <span className="cal-num" aria-hidden="true">{c.jd}</span>
              <span className="sr-only">{label}</span>
              {hol.map((h) => <span key={h.id} className="chip holiday" title={h.title}>{h.title}</span>)}
              {evs.slice(0, MAX_CHIPS).map((e) => (
                <Link
                  key={`${e.id}-${e.employeeId}`}
                  className="chip"
                  style={{ background: e.color }}
                  to={`/requests/${e.id}`}
                  title={`${e.employeeName} · ${e.label}${eventTime(e)}`}
                >
                  {e.employeeName.split(" ")[0]} · {e.label}{eventTime(e)}
                </Link>
              ))}
              {evs.length > MAX_CHIPS && <span className="cal-more">+{evs.length - MAX_CHIPS} مورد دیگر</span>}
            </div>
          );
        })}
      </div>
      <div className="legend" aria-hidden="true">
        <span><i style={{ background: "var(--accent)" }} />تعطیل رسمی</span>
        <span><i style={{ background: "#6b7280" }} />غایب (نوع نامشخص)</span>
        <span><i style={{ outline: "2px solid var(--accent)", outlineOffset: -1, background: "transparent" }} />امروز</span>
      </div>
    </>
  );
}

const DAY_W = 28;
const DAY_GAP = 2;
const STRIDE = DAY_W + DAY_GAP;
const WINDOW_DAYS = 21;

export function TimelinePage() {
  const [offset, setOffset] = useState(0);
  const today = todayIso();
  const from = addDaysIso(today, offset);
  const to = addDaysIso(from, WINDOW_DAYS - 1);
  const { data, error, loading, reload } = useAsync(() => api.calendar(from, to, "team"), [from, to]);
  const days = useMemo(() => Array.from({ length: WINDOW_DAYS }, (_, i) => addDaysIso(from, i)), [from]);
  const people = Array.from(new Set((data ?? []).map((e) => e.employeeName))).sort((a, b) => a.localeCompare(b, "fa"));
  const trackWidth = WINDOW_DAYS * STRIDE - DAY_GAP;
  const todayIndex = days.indexOf(today);

  return (
    <>
      <PageHeader
        title="نوار زمانی تیم"
        subtitle={`از ${formatJalaliSafe(from)} تا ${formatJalaliSafe(to)}`}
        actions={(
          <>
            <Button variant="secondary" size="sm" onClick={() => setOffset((o) => o - 7)}>هفته قبل</Button>
            <Button variant="secondary" size="sm" onClick={() => setOffset((o) => o + 7)}>هفته بعد</Button>
            <Button variant="ghost" size="sm" disabled={offset === 0} onClick={() => setOffset(0)}>امروز</Button>
          </>
        )}
      />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      <Card>
        {loading && !data ? <LoadingBlock /> : (
          <div className="timeline" tabIndex={0} role="region" aria-label="نوار زمانی غیبت‌های تیم">
            <div className="timeline-row">
              <div className="timeline-name" aria-hidden="true" />
              <div className="timeline-days" style={{ gridTemplateColumns: `repeat(${WINDOW_DAYS}, ${DAY_W}px)` }} aria-hidden="true">
                {days.map((d) => {
                  const jd = formatJalaliSafe(d).split("/")[2] ?? "";
                  const cls = [d === today ? "today" : "", pythonWeekday(d) === 4 ? "weekend" : ""].filter(Boolean).join(" ");
                  return <span key={d} className={cls}>{jd.replace(/^0/, "")}</span>;
                })}
              </div>
            </div>
            {people.map((name) => {
              const evs = (data ?? []).filter((e) => e.employeeName === name && e.end >= from && e.start <= to);
              return (
                <div key={name} className="timeline-row">
                  <div className="timeline-name" title={name}>{name}</div>
                  <div className="timeline-track" style={{ width: trackWidth }}>
                    {todayIndex >= 0 && <span className="timeline-today" style={{ insetInlineStart: todayIndex * STRIDE + DAY_W / 2 }} aria-hidden="true" />}
                    {evs.map((e) => {
                      const s = Math.max(0, days.indexOf(e.start < from ? from : e.start));
                      const endIdx = days.indexOf(e.end > to ? to : e.end);
                      const en = endIdx < 0 ? days.length - 1 : endIdx;
                      const w = Math.max(1, en - s + 1);
                      return (
                        <Link
                          key={`${e.id}-${e.start}`}
                          className="timeline-bar"
                          to={`/requests/${e.id}`}
                          title={`${name} · ${e.label}${eventTime(e)} · ${formatJalaliSafe(e.start)} تا ${formatJalaliSafe(e.end)}`}
                          style={{ insetInlineStart: s * STRIDE, width: w * STRIDE - DAY_GAP, background: e.color }}
                        >
                          {e.label}{eventTime(e)}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
            {!people.length && <Empty title="رویدادی در این بازه نیست." />}
          </div>
        )}
      </Card>
    </>
  );
}

type CoverageRow = Awaited<ReturnType<typeof api.coverage>>[number];

export function CoveragePage() {
  const from = todayIso();
  const to = addDaysIso(from, 13);
  const { data, error, loading, reload } = useAsync(() => api.coverage(from, to), [from, to]);
  const columns: Column<CoverageRow>[] = [
    { key: "date", label: "تاریخ", render: (r) => formatJalaliSafe(r.date) },
    { key: "departmentName", label: "واحد" },
    { key: "awayCount", label: "غایب" },
    { key: "headcount", label: "نفرات" },
    {
      key: "ratio",
      label: "نسبت",
      render: (r) => {
        const pct = r.headcount ? Math.round((r.awayCount / r.headcount) * 100) : 0;
        return (
          <div className="cov-cell">
            <Meter value={r.awayCount} max={r.headcount} label={`نسبت غایبان ${r.departmentName} در ${formatJalaliSafe(r.date)}`} tone={pct >= 50 ? "danger" : pct >= 30 ? "warn" : "primary"} />
            <span>{pct}٪</span>
          </div>
        );
      },
    },
  ];
  return (
    <>
      <PageHeader title="پوشش تیم" subtitle={`شمارش غیبت بدون افشای نوع مرخصی · ${formatJalaliSafe(from)} تا ${formatJalaliSafe(to)}`} />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      {loading && !data ? <LoadingBlock /> : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(r) => `${r.date}-${r.departmentName}`} caption="پوشش تیم در دو هفته آینده" />
      )}
    </>
  );
}
