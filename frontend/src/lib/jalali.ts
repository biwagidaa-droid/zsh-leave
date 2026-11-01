/** تبدیل شمسی ↔ میلادی؛ هم‌خوان با backend/zsh_core/jalali.py */

export const MIN_YEAR = 1343;
export const MAX_YEAR = 1472;
const LEAP_REMAINDERS = new Set([1, 5, 9, 13, 17, 22, 26, 30]);
const ANCHOR_YEAR = 1400;
const ANCHOR = { y: 2021, m: 3, d: 21 };
export const MONTH_NAMES = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
] as const;
/** ترتیب نمایش ایرانی: شنبه تا جمعه */
export const WEEKDAY_NAMES = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"] as const;

export function saturdayIndex(iso: string): number {
  return (pythonWeekday(iso) + 2) % 7;
}

export class JalaliError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "JalaliError";
  }
}

export function isLeap(jy: number): boolean {
  return LEAP_REMAINDERS.has(((jy % 33) + 33) % 33);
}

export function yearLength(jy: number): number {
  return isLeap(jy) ? 366 : 365;
}

export function monthLength(jy: number, jm: number): number {
  if (jm < 1 || jm > 12) throw new JalaliError(`ماه نامعتبر: ${jm}`);
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isLeap(jy) ? 30 : 29;
}

function checkYear(jy: number): void {
  if (jy < MIN_YEAR || jy > MAX_YEAR) {
    throw new JalaliError(`سال ${jy} خارج از بازه پشتیبانی‌شده ${MIN_YEAR}–${MAX_YEAR} است`);
  }
}

function fromUtcDay(n: number): { y: number; m: number; d: number } {
  const dt = new Date(Date.UTC(1970, 0, 1 + n));
  return { y: dt.getUTCFullYear(), m: dt.getUTCMonth() + 1, d: dt.getUTCDate() };
}

function toUtcDay(y: number, m: number, d: number): number {
  return Math.floor(Date.UTC(y, m - 1, d) / 86400000);
}

const yearStartCache = new Map<number, number>();

function yearStartUtcDay(jy: number): number {
  const cached = yearStartCache.get(jy);
  if (cached !== undefined) return cached;
  let day = toUtcDay(ANCHOR.y, ANCHOR.m, ANCHOR.d);
  if (jy >= ANCHOR_YEAR) {
    for (let y = ANCHOR_YEAR; y < jy; y++) day += yearLength(y);
  } else {
    for (let y = ANCHOR_YEAR - 1; y >= jy; y--) day -= yearLength(y);
  }
  yearStartCache.set(jy, day);
  return day;
}

export type GDate = { y: number; m: number; d: number };
export type JDate = { jy: number; jm: number; jd: number };

export function toGregorian(jy: number, jm: number, jd: number): GDate {
  checkYear(jy);
  const ml = monthLength(jy, jm);
  if (jd < 1 || jd > ml) throw new JalaliError(`روز نامعتبر: ${jy}/${jm}/${jd}`);
  let offset = jd - 1;
  for (let m = 1; m < jm; m++) offset += monthLength(jy, m);
  return fromUtcDay(yearStartUtcDay(jy) + offset);
}

export function fromGregorian(g: GDate): JDate {
  const day = toUtcDay(g.y, g.m, g.d);
  let jy = g.y - 622;
  while (yearStartUtcDay(jy) > day) jy -= 1;
  while (yearStartUtcDay(jy + 1) <= day) jy += 1;
  checkYear(jy);
  let days = day - yearStartUtcDay(jy);
  for (let jm = 1; jm <= 12; jm++) {
    const ml = monthLength(jy, jm);
    if (days < ml) return { jy, jm, jd: days + 1 };
    days -= ml;
  }
  throw new JalaliError("خطای داخلی تبدیل تاریخ");
}

export function isoToG(iso: string): GDate {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return { y, m, d };
}

export function gToIso(g: GDate): string {
  return `${String(g.y).padStart(4, "0")}-${String(g.m).padStart(2, "0")}-${String(g.d).padStart(2, "0")}`;
}

export function formatJalali(iso: string, withMonthName = false): string {
  const j = fromGregorian(isoToG(iso));
  if (withMonthName) return `${j.jd} ${MONTH_NAMES[j.jm - 1]} ${j.jy}`;
  return `${j.jy}/${String(j.jm).padStart(2, "0")}/${String(j.jd).padStart(2, "0")}`;
}

const FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
const AR_DIGITS = "٠١٢٣٤٥٦٧٨٩";

export function toLatinDigits(text: string): string {
  return text.replace(/[۰-۹٠-٩]/g, (ch) => {
    const fa = FA_DIGITS.indexOf(ch);
    if (fa >= 0) return String(fa);
    const ar = AR_DIGITS.indexOf(ch);
    return ar >= 0 ? String(ar) : ch;
  });
}

export function toFaDigits(text: string): string {
  return text.replace(/\d/g, (d) => FA_DIGITS[Number(d)]);
}

export function parseJalali(text: string): string {
  const parts = toLatinDigits(text.trim()).replace(/-/g, "/").split("/");
  if (parts.length !== 3 || !parts.every((p) => /^\d+$/.test(p))) {
    throw new JalaliError("قالب تاریخ باید سال/ماه/روز باشد");
  }
  const g = toGregorian(Number(parts[0]), Number(parts[1]), Number(parts[2]));
  return gToIso(g);
}

export function todayIso(): string {
  const n = new Date();
  return gToIso({ y: n.getFullYear(), m: n.getMonth() + 1, d: n.getDate() });
}

export function addDaysIso(iso: string, days: number): string {
  const g = isoToG(iso);
  return gToIso(fromUtcDay(toUtcDay(g.y, g.m, g.d) + days));
}

/** JS Sunday=0 → Python Monday=0 */
export function pythonWeekday(iso: string): number {
  const g = isoToG(iso);
  const js = new Date(Date.UTC(g.y, g.m - 1, g.d)).getUTCDay();
  return (js + 6) % 7;
}

export function jalaliNow(): JDate {
  const n = new Date();
  return fromGregorian({ y: n.getFullYear(), m: n.getMonth() + 1, d: n.getDate() });
}

export function daysInRange(startIso: string, endIso: string, limit = Number.POSITIVE_INFINITY): string[] {
  const out: string[] = [];
  let cur = startIso;
  while (cur <= endIso) {
    out.push(cur);
    if (out.length > limit) break;
    cur = addDaysIso(cur, 1);
  }
  return out;
}

/* ───────── کمکی‌های ایمن برای نمایش (هرگز استثنا پرتاب نمی‌کنند) ───────── */

const ISO_RE = /^\d{4}-\d{2}-\d{2}/;

export function isIsoDate(value: string): boolean {
  return ISO_RE.test(value);
}

/** نسخه امن formatJalali: برای مقدار نامعتبر یا خارج از بازه، «—» برمی‌گرداند و صفحه را نمی‌شکند. */
export function formatJalaliSafe(iso: string | null | undefined, withMonthName = false, fallback = "—"): string {
  if (!iso || !isIsoDate(iso)) return fallback;
  try {
    return formatJalali(iso, withMonthName);
  } catch {
    return fallback;
  }
}

/** تاریخ شمسی + ساعت محلی (برای رویدادهایی مثل Job و حسابرسی). */
export function formatJalaliDateTime(iso: string | null | undefined, fallback = "—"): string {
  if (!iso) return fallback;
  if (iso.length <= 10) return formatJalaliSafe(iso, false, fallback);
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return formatJalaliSafe(iso, false, fallback);
  try {
    const j = fromGregorian({ y: d.getFullYear(), m: d.getMonth() + 1, d: d.getDate() });
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${j.jy}/${String(j.jm).padStart(2, "0")}/${String(j.jd).padStart(2, "0")} ${hh}:${mm}`;
  } catch {
    return fallback;
  }
}

/** جابه‌جایی ماه شمسی؛ اگر از بازه پشتیبانی‌شده بیرون بزند null برمی‌گرداند (به‌جای کرش). */
export function shiftJalaliMonth(view: { jy: number; jm: number }, delta: number): { jy: number; jm: number } | null {
  const index = view.jy * 12 + (view.jm - 1) + delta;
  const jy = Math.floor(index / 12);
  const jm = (index % 12 + 12) % 12 + 1;
  if (jy < MIN_YEAR || jy > MAX_YEAR) return null;
  return { jy, jm };
}

/** نام روز هفته بر اساس شاخص پایتون (دوشنبه=۰ … یکشنبه=۶) — هم‌خوان با workDays در Backend. */
export const PY_WEEKDAY_LABELS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"] as const;

/** ایزو تاریخ از سال/ماه/روز شمسی یا null در صورت نامعتبر بودن. */
export function jalaliToIsoSafe(jy: number, jm: number, jd: number): string | null {
  try {
    return gToIso(toGregorian(jy, jm, jd));
  } catch {
    return null;
  }
}

/** تبدیل ورودی عددی کاربر (ارقام فارسی/عربی، جداکننده «٫» یا «،») به رشته‌ای قابل ارسال. */
export function normalizeNumberInput(text: string): string {
  return toLatinDigits(text).replace(/[٫،]/g, ".").replace(/\s+/g, "").trim();
}
