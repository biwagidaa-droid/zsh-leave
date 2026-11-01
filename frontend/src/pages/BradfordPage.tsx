import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { asApiError, errorMessage } from "../api/errors";
import type { BradfordNote, Employee, LeaveRequest } from "../api/types";
import { ColumnChart, DonutChart, type ChartDatum } from "../components/charts";
import { JalaliDateField } from "../components/JalaliDateField";
import {
  Badge, Banner, Button, Card, Checkbox, DataTable, Empty, ErrorState, Field, Input, LoadingBlock, Modal,
  PageHeader, Segmented, Stat, Textarea, type Column,
} from "../components/ui";
import {
  BRADFORD_LEVEL_LABEL, BRADFORD_NOTE, previousWindow, windowForPreset, type BradfordLevel, type RangePreset,
} from "../lib/bradford";
import {
  DEFAULT_WORK_WEEKDAYS, analyzeEmployee, bradfordConfigFromSettings, levelCounts, monthWindows, validThresholds,
  validWindow, type AbsenceRecord, type BradfordConfig, type BradfordEmployeeResult,
} from "../lib/bradfordAnalysis";
import { holidayIsosForRange } from "../lib/holidayDates";
import { formatJalaliDateTime, formatJalaliSafe, todayIso } from "../lib/jalali";
import { useAsync } from "../lib/useAsync";
import { useToast } from "../state/Toast";

const LEVEL_TONE: Record<BradfordLevel, "ok" | "info" | "warn" | "danger" | "accent"> = {
  normal: "ok", attention: "info", warn: "warn", serious: "danger", review: "accent",
};
const LEVEL_COLOR: Record<BradfordLevel, string> = {
  normal: "var(--chart-3)", attention: "var(--chart-5)", warn: "var(--chart-2)", serious: "var(--chart-4)", review: "var(--chart-6)",
};
const LEVELS: BradfordLevel[] = ["normal", "attention", "warn", "serious", "review"];
const PRESETS = [
  { id: "30", label: "۳۰ روز" }, { id: "90", label: "۹۰ روز" }, { id: "180", label: "۱۸۰ روز" },
  { id: "365", label: "۳۶۵ روز" }, { id: "custom", label: "سفارشی" },
];
const MAX_PAGES = 40;

type Loaded = {
  employees: Employee[];
  records: LeaveRequest[];
  /** درخواست‌هایی که شمارش کل بیش از صفحه‌های خوانده‌شده بود؛ در این حالت امتیاز نمایش داده نمی‌شود */
  truncated: boolean;
  cfg: BradfordConfig;
  holidays: Awaited<ReturnType<typeof api.holidays>>;
  workDays: Record<number, number[]>;
  notes: BradfordNote[];
  types: { key: string; labelFa: string }[];
};

async function loadAll(): Promise<Loaded> {
  const [employees, settings, holidays, notes, types] = await Promise.all([
    api.employees(),
    api.settings(),
    api.holidays(),
    api.bradfordNotes(),
    api.listTypes(),
  ]);
  const records: LeaveRequest[] = [];
  let truncated = false;
  for (let page = 1; page <= MAX_PAGES; page += 1) {
    const res = await api.listRequests({ page: page > 1 ? page : undefined });
    records.push(...res.results);
    if (records.length >= res.count || !res.results.length) break;
    if (page === MAX_PAGES) truncated = true;
  }
  const withAbsence = new Set(records.map((r) => r.employeeId));
  const workDays: Record<number, number[]> = {};
  await Promise.all(employees.filter((e) => withAbsence.has(e.id)).map(async (e) => {
    const periods = await api.contracts(e.id);
    const now = todayIso();
    const cur = periods.find((p) => p.start <= now && (p.end == null || p.end >= now));
    if (!cur?.workDays.length) {
      throw new Error("برای محاسبه Bradford، الگوی کاری معتبر کارکنان باید از سرور دریافت شود");
    }
    workDays[e.id] = cur.workDays;
  }));
  return {
    employees, records, truncated, cfg: bradfordConfigFromSettings(settings),
    holidays, workDays, notes, types: types.map((t) => ({ key: t.key, labelFa: t.labelFa })),
  };
}

type Row = {
  employee: Employee;
  cur: BradfordEmployeeResult;
  prev: BradfordEmployeeResult;
  customWork: boolean;
};

export function BradfordPage() {
  const { data, error, loading, reload } = useAsync(loadAll, []);
  const today = todayIso();
  const [preset, setPreset] = useState<RangePreset>("90");
  const [customFrom, setCustomFrom] = useState(windowForPreset("90", today).from);
  const [customTo, setCustomTo] = useState(today);
  const [company, setCompany] = useState("");
  const [department, setDepartment] = useState("");
  const [manager, setManager] = useState("");
  const [detailId, setDetailId] = useState<number | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const win = useMemo(() => windowForPreset(preset, today, customFrom, customTo), [preset, today, customFrom, customTo]);
  const winOk = validWindow(win.from, win.to);
  const prevWin = useMemo(() => (winOk ? previousWindow(win.from, win.to) : null), [win, winOk]);

  const employees = useMemo(() => (data?.employees ?? []).filter((e) => e.isActive), [data]);
  const companies = useMemo(() => [...new Set(employees.map((e) => e.companyName))].sort(), [employees]);
  const departments = useMemo(() => [...new Set(employees.filter((e) => !company || e.companyName === company).map((e) => e.departmentName))].filter(Boolean).sort(), [employees, company]);
  const managers = useMemo(() => [...new Set(employees.map((e) => e.managerName).filter((m): m is string => !!m))].sort(), [employees]);
  const filtered = useMemo(
    () => employees.filter((e) => (!company || e.companyName === company) && (!department || e.departmentName === department) && (!manager || e.managerName === manager)),
    [employees, company, department, manager],
  );

  const rows: Row[] = useMemo(() => {
    if (!data || !winOk || !prevWin || data.truncated) return [];
    const recs = new Map<number, AbsenceRecord[]>();
    for (const r of data.records) {
      const list = recs.get(r.employeeId) ?? [];
      list.push({
        employeeId: r.employeeId, status: r.status, start: r.start, end: r.end, type: r.type,
        durationKind: r.durationKind, durationMinutes: r.durationMinutes,
      });
      recs.set(r.employeeId, list);
    }
    const hol = new Set([...holidayIsosForRange(data.holidays, prevWin.from, win.to)]);
    return filtered.map((employee) => {
      const own = recs.get(employee.id) ?? [];
      const wd = data.workDays[employee.id];
      const ctx = { workWeekdays: wd ?? DEFAULT_WORK_WEEKDAYS, holidays: hol };
      return {
        employee, customWork: !!wd,
        cur: analyzeEmployee(own, win, ctx, data.cfg, today),
        prev: analyzeEmployee(own, prevWin, ctx, data.cfg, today),
      };
    });
  }, [data, winOk, win, prevWin, filtered, today]);

  const totals = useMemo(() => ({
    spells: rows.reduce((a, r) => a + r.cur.spells, 0),
    days: Math.round(rows.reduce((a, r) => a + r.cur.days, 0) * 100) / 100,
    prevSpells: rows.reduce((a, r) => a + r.prev.spells, 0),
    prevDays: Math.round(rows.reduce((a, r) => a + r.prev.days, 0) * 100) / 100,
    avg: rows.length ? Math.round((rows.reduce((a, r) => a + r.cur.score, 0) / rows.length) * 10) / 10 : 0,
    prevAvg: rows.length ? Math.round((rows.reduce((a, r) => a + r.prev.score, 0) / rows.length) * 10) / 10 : 0,
  }), [rows]);

  const levelData: ChartDatum[] = useMemo(() => {
    const c = levelCounts(rows.map((r) => r.cur));
    return LEVELS.map((l) => ({ label: BRADFORD_LEVEL_LABEL[l], value: c[l], color: LEVEL_COLOR[l] }));
  }, [rows]);

  const deptData = useMemo(() => {
    const m = new Map<string, { n: number; score: number; days: number; spells: number }>();
    for (const r of rows) {
      const k = r.employee.departmentName || "بدون واحد";
      const v = m.get(k) ?? { n: 0, score: 0, days: 0, spells: 0 };
      v.n += 1; v.score += r.cur.score; v.days += r.cur.days; v.spells += r.cur.spells;
      m.set(k, v);
    }
    return [...m.entries()].map(([name, v]) => ({
      name, n: v.n, avg: Math.round((v.score / v.n) * 10) / 10, days: Math.round(v.days * 100) / 100, spells: v.spells,
    })).sort((a, b) => b.avg - a.avg);
  }, [rows]);

  const trendData: ChartDatum[] = useMemo(() => {
    if (!data || !winOk || data.truncated) return [];
    const recs = data.records;
    const hol = new Set(holidayIsosForRange(data.holidays, win.from, win.to));
    return monthWindows(win.from, win.to).map((m) => {
      let days = 0; let spells = 0; let score = 0;
      for (const e of filtered) {
        const res = analyzeEmployee(
          recs.filter((r) => r.employeeId === e.id).map((r) => ({
            employeeId: r.employeeId, status: r.status, start: r.start, end: r.end, type: r.type,
            durationKind: r.durationKind, durationMinutes: r.durationMinutes,
          })),
          { from: m.from, to: m.to }, { workWeekdays: data.workDays[e.id] ?? DEFAULT_WORK_WEEKDAYS, holidays: hol }, data.cfg, today,
        );
        days += res.days; spells += res.spells; score += res.score;
      }
      const avg = filtered.length ? Math.round((score / filtered.length) * 10) / 10 : 0;
      return { label: m.label, value: Math.round(days * 100) / 100, hint: `${spells} دوره · میانگین امتیاز ماه: ${avg}` };
    });
  }, [data, winOk, win, filtered, today]);

  const top10 = useMemo(() => [...rows].filter((r) => r.cur.score > 0).sort((a, b) => b.cur.score - a.cur.score || b.cur.days - a.cur.days).slice(0, 10), [rows]);
  const needReview = useMemo(() => rows.filter((r) => r.cur.level === "review").sort((a, b) => b.cur.score - a.cur.score), [rows]);

  const delta = (cur: number, prev: number) => (cur === prev ? "بدون تغییر" : `${cur > prev ? "+" : "−"}${Math.round(Math.abs(cur - prev) * 10) / 10}`);

  const columns: Column<Row>[] = [
    { key: "rank", label: "#", render: (r) => top10.indexOf(r) + 1 },
    { key: "name", label: "کارمند", render: (r) => <button type="button" className="link-btn" onClick={() => setDetailId(r.employee.id)}>{r.employee.displayName}</button> },
    { key: "dept", label: "واحد", render: (r) => r.employee.departmentName || "—" },
    { key: "S", label: "دوره‌ها", render: (r) => r.cur.spells },
    { key: "D", label: "روز", render: (r) => r.cur.days },
    { key: "BF", label: "امتیاز", render: (r) => <strong>{r.cur.score}</strong> },
    { key: "level", label: "وضعیت", render: (r) => <Badge tone={LEVEL_TONE[r.cur.level]}>{BRADFORD_LEVEL_LABEL[r.cur.level]}</Badge> },
    { key: "delta", label: "نسبت به دوره قبل", render: (r) => delta(r.cur.score, r.prev.score) },
  ];

  const detail = rows.find((r) => r.employee.id === detailId) ?? null;

  if (loading && !data) return <LoadingBlock label="در حال بارگذاری داده‌های تحلیل…" />;
  if (error) return <ErrorState message={error} onRetry={() => void reload()} />;
  if (!data) return null;

  return (
    <>
      <PageHeader
        title="تحلیل Bradford Factor"
        subtitle="BF = S² × D — فقط برای نقش‌های مجاز منابع انسانی"
        actions={<Button variant="secondary" size="sm" onClick={() => setShowSettings((v) => !v)}>{showSettings ? "بستن تنظیمات تحلیل" : "تنظیمات تحلیل"}</Button>}
      />
      <Banner tone="info">
        {BRADFORD_NOTE} امتیاز به‌تنهایی مبنای اقدام انضباطی نیست. فقط مرخصی‌های <strong>تأییدشده</strong> از انواع مشمول
        ({data.cfg.includeTypes.length ? data.cfg.includeTypes.map((k) => data.types.find((t) => t.key === k)?.labelFa ?? k).join("، ") : "هیچ"})
        و فقط روزهای کاری گذشته محاسبه می‌شوند؛ مرخصی برنامه‌ریزی‌شده (مثل استحقاقی) غیبت غیرموجه تلقی نمی‌شود.
        {data.cfg.includeHourly ? ` مرخصی ساعتی با تبدیل ${data.cfg.hourlyMinutesPerDay} دقیقه = ۱ روز لحاظ شده است.` : " مرخصی ساعتی در محاسبه نیست (سیاست تبدیل فعال نشده)."}
      </Banner>
      {showSettings && <BradfordSettings cfg={data.cfg} types={data.types} onSaved={() => void reload()} />}
      {!data.cfg.enabled ? (
        <Card><Empty title="تحلیل Bradford در تنظیمات غیرفعال است" hint="کلید bradford.enabled را فعال کنید." /></Card>
      ) : (
        <>
          <div className="toolbar" role="group" aria-label="بازه تحلیل">
            <Segmented label="بازه تحلیل" value={preset} onChange={(v) => setPreset(v as RangePreset)} items={PRESETS} />
          </div>
          {preset === "custom" && (
            <div className="grid grid-2">
              <Field label="از تاریخ"><JalaliDateField value={customFrom} max={customTo || undefined} onChange={setCustomFrom} /></Field>
              <Field label="تا تاریخ" error={!winOk ? "بازه نامعتبر یا بیش از ۱۱۰۰ روز است" : undefined}><JalaliDateField value={customTo} min={customFrom || undefined} onChange={setCustomTo} /></Field>
            </div>
          )}
          <div className="toolbar" role="search">
            <select aria-label="فیلتر شرکت" value={company} onChange={(e) => { setCompany(e.target.value); setDepartment(""); }}>
              <option value="">همه شرکت‌ها</option>
              {companies.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select aria-label="فیلتر دپارتمان" value={department} onChange={(e) => setDepartment(e.target.value)}>
              <option value="">همه دپارتمان‌ها</option>
              {departments.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <select aria-label="فیلتر مدیر" value={manager} onChange={(e) => setManager(e.target.value)}>
              <option value="">همه مدیران</option>
              {managers.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <span className="hint">بازه: {formatJalaliSafe(win.from)} تا {formatJalaliSafe(win.to)}</span>
          </div>
          {data.truncated && (
            <Banner tone="danger">
              فهرست غیبت‌ها کامل بارگذاری نشد؛ برای جلوگیری از امتیاز نادرست، تحلیل نمایش داده نمی‌شود. به یک API تجمیعی Bradford در Backend نیاز است.
            </Banner>
          )}
          {!data.truncated && winOk && (
            <>
              <div className="grid grid-4 mb">
                <Stat label="کارکنان تحلیل‌شده" value={String(rows.length)} />
                <Stat label="دوره‌های غیبت" value={String(totals.spells)} hint={`دوره قبل: ${totals.prevSpells} (${delta(totals.spells, totals.prevSpells)})`} />
                <Stat label="مجموع روزهای غیبت" value={String(totals.days)} hint={`دوره قبل: ${totals.prevDays} (${delta(totals.days, totals.prevDays)})`} />
                <Stat label="میانگین امتیاز" value={String(totals.avg)} hint={`دوره قبل: ${totals.prevAvg} (${delta(totals.avg, totals.prevAvg)})`} />
              </div>
              <div className="grid grid-2 mb">
                <Card title="توزیع سطوح"><DonutChart title="توزیع سطوح Bradford" data={levelData} totalLabel="نفر" emptyTitle="کارمندی برای تحلیل نیست" /></Card>
                <Card title="روند ماهانه (روز غیبت)"><ColumnChart title="روند ماهانه روزهای غیبت" data={trendData} valueLabel="روز غیبت" emptyTitle="غیبت مشمولی در این بازه نیست" /></Card>
              </div>
              <Card title="مقایسه واحدهای سازمانی">
                {deptData.length ? (
                  <div className="grid grid-2">
                    <ColumnChart title="میانگین امتیاز واحدها" valueLabel="میانگین امتیاز" data={deptData.map((d) => ({ label: d.name, value: d.avg, hint: `${d.n} نفر · ${d.spells} دوره · ${d.days} روز` }))} />
                    <DataTable
                      columns={[
                        { key: "name", label: "واحد" }, { key: "n", label: "نفر" }, { key: "spells", label: "دوره" },
                        { key: "days", label: "روز" }, { key: "avg", label: "میانگین امتیاز" },
                      ] as Column<(typeof deptData)[number]>[]}
                      rows={deptData} rowKey={(d) => d.name} caption="مقایسه واحدها"
                    />
                  </div>
                ) : <Empty title="داده‌ای نیست" />}
              </Card>
              <div className="mt"><Card title="۱۰ کارمند با بالاترین امتیاز">
                <DataTable columns={columns} rows={top10} rowKey={(r) => r.employee.id} caption="بالاترین امتیازهای Bradford" empty={<Empty title="در این بازه غیبت مشمولی ثبت نشده است" />} />
              </Card></div>
              <div className="mt"><Card title={`نیازمند بررسی HR (امتیاز ≥ ${data.cfg.thresholds.review})`}>
                {needReview.length ? (
                  <ul className="list">
                    {needReview.map((r) => (
                      <li key={r.employee.id}>
                        <button type="button" className="link-btn" onClick={() => setDetailId(r.employee.id)}>{r.employee.displayName} · {r.employee.departmentName}</button>
                        <span><strong>{r.cur.score}</strong> <Badge tone="accent">{BRADFORD_LEVEL_LABEL.review}</Badge></span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="muted">موردی در این سطح نیست.</p>}
              </Card></div>
            </>
          )}
        </>
      )}
      {detail && data && (
        <EmployeeDetail row={detail} data={data} onClose={() => setDetailId(null)} win={win} onNote={() => void reload()} />
      )}
    </>
  );
}

function EmployeeDetail({
  row, data, win, onClose, onNote,
}: { row: Row; data: Loaded; win: { from: string; to: string }; onClose: () => void; onNote: () => void }) {
  const toast = useToast();
  const existing = data.notes.find((n) => n.employeeId === row.employee.id);
  const [note, setNote] = useState(existing?.body ?? "");
  const [busy, setBusy] = useState(false);
  const today = todayIso();
  const hol = useMemo(() => new Set(holidayIsosForRange(data.holidays, addYear(today), today)), [data.holidays, today]);
  const recs: AbsenceRecord[] = data.records.filter((r) => r.employeeId === row.employee.id).map((r) => ({
    employeeId: r.employeeId, status: r.status, start: r.start, end: r.end, type: r.type,
    durationKind: r.durationKind, durationMinutes: r.durationMinutes,
  }));
  const ctx = { workWeekdays: data.workDays[row.employee.id] ?? DEFAULT_WORK_WEEKDAYS, holidays: hol };
  const spans = [30, 90, 180, 365].map((d) => {
    const w = windowForPreset(String(d) as RangePreset, today);
    return { d, res: analyzeEmployee(recs, w, ctx, data.cfg, today) };
  });
  const list = data.records.filter((r) => r.employeeId === row.employee.id && r.status === "APPROVED" && r.end >= win.from && r.start <= win.to)
    .sort((a, b) => b.start.localeCompare(a.start));

  const save = async () => {
    setBusy(true);
    try {
      await api.saveBradfordNote(row.employee.id, note.trim());
      toast("یادداشت ذخیره شد", "success");
      onNote();
    } catch (e) {
      toast(errorMessage(e), "danger");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title={`جزئیات ${row.employee.displayName}`} onClose={onClose}>
      <p className="hint">{row.employee.departmentName} · {row.employee.companyName}{row.customWork ? "" : " · الگوی کاری پیش‌فرض سازمان (قرارداد در دسترس نبود)"}</p>
      <div className="grid grid-3 mb">
        <Stat label="دوره‌ها (S)" value={String(row.cur.spells)} />
        <Stat label="روز غیبت (D)" value={String(row.cur.days)} />
        <Stat label="امتیاز" value={String(row.cur.score)} hint={BRADFORD_LEVEL_LABEL[row.cur.level]} />
      </div>
      <DataTable
        columns={[
          { key: "d", label: "بازه", render: (x) => `${x.d} روز اخیر` },
          { key: "s", label: "دوره", render: (x) => x.res.spells },
          { key: "days", label: "روز", render: (x) => x.res.days },
          { key: "score", label: "امتیاز", render: (x) => <><strong>{x.res.score}</strong> <Badge tone={LEVEL_TONE[x.res.level]}>{BRADFORD_LEVEL_LABEL[x.res.level]}</Badge></> },
        ] as Column<(typeof spans)[number]>[]}
        rows={spans} rowKey={(x) => x.d} caption="امتیاز در بازه‌های استاندارد"
      />
      <h3 className="mt">غیبت‌های تأییدشده در بازه انتخابی</h3>
      {list.length ? (
        <ul className="list">
          {list.map((r) => (
            <li key={r.id}>
              <Link to={`/requests/${r.id}`}>{r.typeLabel ?? "غیبت"} · {formatJalaliSafe(r.start)}{r.start !== r.end ? ` تا ${formatJalaliSafe(r.end)}` : ""}</Link>
              <span>
                {data.cfg.includeTypes.includes(r.type ?? "") ? <Badge tone="info">مشمول</Badge> : <Badge tone="muted">غیرمشمول</Badge>}
                {r.durationKind === "hourly" && <span className="kind-tag">ساعتی</span>}
              </span>
            </li>
          ))}
        </ul>
      ) : <p className="muted">غیبت تأییدشده‌ای در این بازه نیست.</p>}
      {row.cur.skippedInvalid > 0 && <Banner tone="warn">{row.cur.skippedInvalid} رکورد ناقص/نامعتبر کنار گذاشته شد؛ امتیاز از روی آن‌ها ساخته نشده است.</Banner>}
      <Field label="یادداشت HR" hint={existing ? `آخرین ویرایش: ${existing.authorName} · ${formatJalaliDateTime(existing.updatedAt)}` : "یادداشت فقط برای HR قابل مشاهده است"}>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <p className="hint">{BRADFORD_NOTE}</p>
      <div className="toolbar modal-actions">
        <Button loading={busy} onClick={() => void save()} disabled={note.trim() === (existing?.body ?? "")}>ذخیره یادداشت</Button>
        <Button variant="secondary" onClick={onClose}>بستن</Button>
      </div>
    </Modal>
  );
}

function addYear(iso: string): string {
  // یک سال میلادی به عقب (برای محدوده تعطیلات پنل جزئیات)
  const y = Number(iso.slice(0, 4)) - 1;
  return `${y}${iso.slice(4)}`;
}

function BradfordSettings({ cfg, types, onSaved }: { cfg: BradfordConfig; types: { key: string; labelFa: string }[]; onSaved: () => void }) {
  const toast = useToast();
  const [th, setTh] = useState({ ...cfg.thresholds });
  const [inc, setInc] = useState<string[]>(cfg.includeTypes);
  const [hourly, setHourly] = useState(cfg.includeHourly);
  const [mins, setMins] = useState(String(cfg.hourlyMinutesPerDay));
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    const e: Record<string, string> = {};
    if (!validThresholds(th)) e.th = "آستانه‌ها باید مثبت و اکیداً صعودی باشند";
    if (!Number.isFinite(Number(mins)) || Number(mins) <= 0) e.mins = "عدد مثبت وارد کنید";
    if (!reason.trim()) e.reason = "دلیل تغییر الزامی است";
    setErr(e);
    if (Object.keys(e).length) return;
    const changes: [string, unknown][] = [
      ["bradford.threshold_attention", th.attention], ["bradford.threshold_warn", th.warn],
      ["bradford.threshold_serious", th.serious], ["bradford.threshold_review", th.review],
      ["bradford.include_types", inc.join(",")], ["bradford.include_hourly", hourly],
      ["bradford.hourly_minutes_per_day", Number(mins)],
    ];
    setBusy(true);
    try {
      for (const [k, v] of changes) await api.saveSetting(k, v, reason.trim());
      toast("تنظیمات تحلیل ذخیره شد", "success");
      onSaved();
    } catch (x) {
      toast(asApiError(x).message, "danger");
    } finally {
      setBusy(false);
    }
  };

  const num = (k: keyof typeof th) => (
    <Input value={String(th[k])} inputMode="numeric" dir="ltr" className="ltr-input" onChange={(ev) => setTh((t) => ({ ...t, [k]: Number(ev.target.value) }))} />
  );

  return (
    <Card title="تنظیمات تحلیل (آستانه‌ها و انواع مشمول)">
      <div className="grid grid-4">
        <Field label="نیازمند توجه از" error={err.th}>{num("attention")}</Field>
        <Field label="هشدار از">{num("warn")}</Field>
        <Field label="هشدار جدی از">{num("serious")}</Field>
        <Field label="نیازمند بررسی HR از">{num("review")}</Field>
      </div>
      <fieldset className="field-group">
        <legend>انواع غیبت مشمول</legend>
        <div className="check-row">
          {types.map((t) => (
            <Checkbox key={t.key} label={t.labelFa} checked={inc.includes(t.key)}
              onChange={(e) => setInc((x) => (e.target.checked ? [...x, t.key] : x.filter((k) => k !== t.key)))} />
          ))}
        </div>
      </fieldset>
      <div className="grid grid-2">
        <Checkbox label="مرخصی ساعتی منظور شود (تبدیل به کسری از روز)" checked={hourly} onChange={(e) => setHourly(e.target.checked)} />
        <Field label="دقیقه معادل یک روز" error={err.mins}><Input value={mins} inputMode="numeric" dir="ltr" className="ltr-input" onChange={(e) => setMins(e.target.value)} /></Field>
      </div>
      <Field label="دلیل تغییر (الزامی)" error={err.reason}><Input value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      <p className="hint">هر تغییر در حسابرسی ثبت می‌شود. در حالت Backend واقعی، مجوز تغییر تنظیمات با سرور است.</p>
      <Button loading={busy} onClick={() => void submit()}>ذخیره تنظیمات</Button>
    </Card>
  );
}
