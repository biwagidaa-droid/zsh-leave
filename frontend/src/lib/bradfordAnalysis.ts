import {
  BRADFORD_LEVEL_LABEL, BRADFORD_NOTE, DEFAULT_BRADFORD_THRESHOLDS, bradfordLevel, hourlyMinutesAsDays,
  type BradfordLevel, type BradfordThresholds, type Spell,
} from "./bradford";
import { addDaysIso, daysInRange, isIsoDate, jalaliToIsoSafe, fromGregorian, isoToG, monthLength, MONTH_NAMES, pythonWeekday } from "./jalali";

/** الگوی پیش‌فرض روز کاری (شاخص پایتون؛ دوشنبه=۰): شنبه تا چهارشنبه — فقط وقتی قرارداد کارمند در دسترس نیست. */
export const DEFAULT_WORK_WEEKDAYS = [5, 6, 0, 1, 2];

/** سقف طول بازه برای جلوگیری از حلقه‌های سنگین در مرورگر */
export const MAX_WINDOW_DAYS = 1100;

export type AbsenceRecord = {
  employeeId: number;
  status: string;
  start: string;
  end: string;
  type?: string;
  durationKind?: "daily" | "hourly";
  durationMinutes?: number;
};

export type BradfordConfig = {
  enabled: boolean;
  /** کلید انواع مرخصی مشمول (غیبت‌های برنامه‌ریزی‌شده مثل استحقاقی به‌طور پیش‌فرض مشمول نیستند) */
  includeTypes: string[];
  includeHourly: boolean;
  hourlyMinutesPerDay: number;
  thresholds: BradfordThresholds;
};

export const DEFAULT_BRADFORD_CONFIG: BradfordConfig = {
  enabled: true,
  includeTypes: ["sick"],
  includeHourly: false,
  hourlyMinutesPerDay: 480,
  thresholds: DEFAULT_BRADFORD_THRESHOLDS,
};

function num(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}
function bool(v: unknown, fallback: boolean): boolean {
  if (typeof v === "boolean") return v;
  if (v === "true") return true;
  if (v === "false") return false;
  return fallback;
}

/** آستانه‌ها باید اکیداً صعودی باشند؛ در غیر این صورت پیش‌فرض‌ها به‌کار می‌روند (امتیاز ساختگی/نامنسجم تولید نمی‌شود). */
export function validThresholds(t: BradfordThresholds): boolean {
  return [t.attention, t.warn, t.serious, t.review].every((x) => Number.isFinite(x) && x > 0)
    && t.attention < t.warn && t.warn < t.serious && t.serious < t.review;
}

export function bradfordConfigFromSettings(rows: { key: string; value: unknown }[] | null | undefined): BradfordConfig {
  if (!rows) return DEFAULT_BRADFORD_CONFIG;
  const m = new Map(rows.map((r) => [r.key, r.value]));
  const types = String(m.get("bradford.include_types") ?? "sick").split(",").map((x) => x.trim()).filter(Boolean);
  const thresholds: BradfordThresholds = {
    attention: num(m.get("bradford.threshold_attention"), DEFAULT_BRADFORD_THRESHOLDS.attention),
    warn: num(m.get("bradford.threshold_warn"), DEFAULT_BRADFORD_THRESHOLDS.warn),
    serious: num(m.get("bradford.threshold_serious"), DEFAULT_BRADFORD_THRESHOLDS.serious),
    review: num(m.get("bradford.threshold_review"), DEFAULT_BRADFORD_THRESHOLDS.review),
  };
  return {
    enabled: bool(m.get("bradford.enabled"), true),
    includeTypes: types,
    includeHourly: bool(m.get("bradford.include_hourly"), false),
    hourlyMinutesPerDay: num(m.get("bradford.hourly_minutes_per_day"), 480),
    thresholds: validThresholds(thresholds) ? thresholds : DEFAULT_BRADFORD_THRESHOLDS,
  };
}

export type WorkContext = { workWeekdays: number[]; holidays: ReadonlySet<string> | string[] };

function isWorkDay(iso: string, ctx: WorkContext): boolean {
  const hol = ctx.holidays instanceof Set ? ctx.holidays.has(iso) : (ctx.holidays as string[]).includes(iso);
  return ctx.workWeekdays.includes(pythonWeekday(iso)) && !hol;
}

export type BradfordEmployeeResult = {
  spells: number;
  days: number;
  score: number;
  level: BradfordLevel;
  merged: Spell[];
  /** روزهای غیبت لحاظ‌شده با وزن آن‌ها (مرخصی ساعتی کسری از روز) */
  dayWeights: { date: string; weight: number }[];
  /** تعداد رکوردهای مشمول که در محاسبه آمدند */
  usedRecords: number;
  /** رکوردهای ناقص/نامعتبر که کنار گذاشته شدند (امتیاز از روی آن‌ها ساخته نمی‌شود) */
  skippedInvalid: number;
};

export function validWindow(from: string, to: string): boolean {
  if (!isIsoDate(from) || !isIsoDate(to) || from > to) return false;
  return daysInRange(from, to, MAX_WINDOW_DAYS + 1).length <= MAX_WINDOW_DAYS;
}

/**
 * Bradford برای یک کارمند در یک بازه.
 * - فقط درخواست‌های «تأییدشده»ی نوع مشمول که تاریخشان رسیده است (آینده/برنامه‌ریزی‌شده محاسبه نمی‌شود).
 * - فقط روزهای کاری شمرده می‌شوند (تعطیلات و الگوی کاری رعایت می‌شود).
 * - غیبت‌هایی که بین‌شان هیچ روز کاری نیست (مثلاً با جمعه/تعطیلی جدا شده‌اند) یک دوره‌اند.
 * - مرخصی ساعتی فقط با سیاست تبدیل صریح (include_hourly) و به‌صورت کسری از روز؛ هرگز روز کامل نیست.
 */
export function analyzeEmployee(
  records: AbsenceRecord[],
  window: { from: string; to: string },
  ctx: WorkContext,
  cfg: BradfordConfig,
  today: string,
): BradfordEmployeeResult {
  if (!validWindow(window.from, window.to)) throw new Error("بازه نامعتبر است");
  const to = window.to < today ? window.to : today;
  const weights = new Map<string, number>();
  let used = 0;
  let skippedInvalid = 0;
  for (const r of records) {
    if (r.status !== "APPROVED") continue;
    if (!r.type || !cfg.includeTypes.includes(r.type)) continue;
    if (!isIsoDate(r.start) || !isIsoDate(r.end) || r.start > r.end) { skippedInvalid += 1; continue; }
    const hourly = r.durationKind === "hourly";
    let w = 1;
    if (hourly) {
      if (!cfg.includeHourly) continue;
      const frac = hourlyMinutesAsDays(r.durationMinutes ?? 0, cfg.hourlyMinutesPerDay);
      if (frac == null) { skippedInvalid += 1; continue; }
      w = Math.min(1, frac);
    }
    const s = r.start > window.from ? r.start : window.from;
    const e = r.end < to ? r.end : to;
    if (s > e) continue;
    let counted = false;
    for (const d of daysInRange(s, e, MAX_WINDOW_DAYS + 1)) {
      if (!isWorkDay(d, ctx)) continue;
      weights.set(d, Math.max(weights.get(d) ?? 0, w));
      counted = true;
    }
    if (counted) used += 1;
  }
  const dates = [...weights.keys()].sort();
  const merged: Spell[] = [];
  let prev: string | null = null;
  for (const d of dates) {
    let joins = false;
    if (prev) {
      joins = true;
      for (let x = addDaysIso(prev, 1); x < d; x = addDaysIso(x, 1)) {
        if (isWorkDay(x, ctx)) { joins = false; break; }
      }
    }
    if (joins) merged[merged.length - 1].end = d;
    else merged.push({ start: d, end: d });
    prev = d;
  }
  const days = Math.round([...weights.values()].reduce((a, b) => a + b, 0) * 100) / 100;
  const spells = merged.length;
  const score = Math.round(spells * spells * days * 100) / 100;
  return {
    spells, days, score, level: bradfordLevel(score, cfg.thresholds), merged,
    dayWeights: dates.map((date) => ({ date, weight: weights.get(date) ?? 0 })),
    usedRecords: used, skippedInvalid,
  };
}

export function emptyLevelCounts(): Record<BradfordLevel, number> {
  return { normal: 0, attention: 0, warn: 0, serious: 0, review: 0 };
}

export function levelCounts(results: { level: BradfordLevel }[]): Record<BradfordLevel, number> {
  const out = emptyLevelCounts();
  for (const r of results) out[r.level] += 1;
  return out;
}

export type MonthWindow = { key: string; label: string; from: string; to: string };

/** پنجره‌های ماه شمسی که بازه را می‌پوشانند؛ ماه‌های ناقص در دو سر به بازه برش می‌خورند. */
export function monthWindows(from: string, to: string): MonthWindow[] {
  const out: MonthWindow[] = [];
  if (!validWindow(from, to)) return out;
  const a = fromGregorian(isoToG(from));
  const b = fromGregorian(isoToG(to));
  let jy = a.jy; let jm = a.jm;
  while (jy < b.jy || (jy === b.jy && jm <= b.jm)) {
    const first = jalaliToIsoSafe(jy, jm, 1);
    const last = jalaliToIsoSafe(jy, jm, monthLength(jy, jm));
    if (first && last) {
      out.push({
        key: `${jy}-${jm}`, label: `${MONTH_NAMES[jm - 1]} ${String(jy).slice(2)}`,
        from: first < from ? from : first, to: last > to ? to : last,
      });
    }
    jm += 1;
    if (jm > 12) { jm = 1; jy += 1; }
    if (out.length > 40) break;
  }
  return out;
}

export { BRADFORD_LEVEL_LABEL, BRADFORD_NOTE };
