import { pythonWeekday } from "./jalali";

export type DurationKind = "daily" | "hourly";

const TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

export function parseHm(value: string): { h: number; m: number } | null {
  const t = value.trim();
  const match = TIME_RE.exec(t);
  if (!match) return null;
  return { h: Number(match[1]), m: Number(match[2]) };
}

export function toMinutes(value: string): number | null {
  const p = parseHm(value);
  return p ? p.h * 60 + p.m : null;
}

export function minutesBetween(startHm: string, endHm: string): number | null {
  const a = toMinutes(startHm);
  const b = toMinutes(endHm);
  if (a == null || b == null) return null;
  return b - a;
}

export function formatDurationFa(totalMinutes: number): string {
  if (!Number.isFinite(totalMinutes) || totalMinutes <= 0) return "—";
  const h = Math.floor(totalMinutes / 60);
  const m = totalMinutes % 60;
  if (h === 0) return `${m} دقیقه`;
  if (m === 0) return h === 1 ? "۱ ساعت" : `${h} ساعت`;
  return `${h} ساعت و ${m} دقیقه`;
}

export function workingDaysFromMinutes(minutes: number, workdayMinutes: number): string {
  const denom = workdayMinutes > 0 ? workdayMinutes : 480;
  return (minutes / denom).toFixed(2);
}

export type HourlyPolicy = {
  workdayStart: string;
  workdayEnd: string;
  allowOutsideWorkHours: boolean;
  allowOnHoliday: boolean;
  maxMinutesPerRequest: number;
  workWeekdays: number[];
};

export type HourlyDraft = {
  date: string;
  startTime: string;
  endTime: string;
};

export type ExistingInterval = {
  id?: number;
  employeeId: number;
  status: string;
  start: string;
  end: string;
  durationKind?: DurationKind;
  startTime?: string;
  endTime?: string;
};

const BLOCKING = new Set(["PENDING", "ESCALATED", "APPROVED", "WITHDRAWAL_PENDING"]);

export function rangesOverlap(aStart: string, aEnd: string, bStart: string, bEnd: string): boolean {
  return aStart <= bEnd && bStart <= aEnd;
}

export function timesOverlap(aStart: string, aEnd: string, bStart: string, bEnd: string): boolean {
  const a0 = toMinutes(aStart);
  const a1 = toMinutes(aEnd);
  const b0 = toMinutes(bStart);
  const b1 = toMinutes(bEnd);
  if (a0 == null || a1 == null || b0 == null || b1 == null) return false;
  return a0 < b1 && b0 < a1;
}

export function validateHourlyDraft(
  draft: HourlyDraft,
  policy: HourlyPolicy,
  holidays: string[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!draft.date) errors.date = "تاریخ مرخصی را وارد کنید";
  if (!parseHm(draft.startTime)) errors.startTime = "ساعت شروع نامعتبر است";
  if (!parseHm(draft.endTime)) errors.endTime = "ساعت پایان نامعتبر است";
  const dur = minutesBetween(draft.startTime, draft.endTime);
  if (dur != null && dur <= 0) errors.endTime = "ساعت پایان باید بعد از ساعت شروع باشد";
  if (dur != null && dur > policy.maxMinutesPerRequest) {
    errors.endTime = `سقف مدت مرخصی ساعتی ${formatDurationFa(policy.maxMinutesPerRequest)} است`;
  }
  if (!policy.allowOutsideWorkHours && dur != null && dur > 0) {
    const ws = toMinutes(policy.workdayStart);
    const we = toMinutes(policy.workdayEnd);
    const a = toMinutes(draft.startTime);
    const b = toMinutes(draft.endTime);
    if (ws != null && we != null && a != null && b != null && (a < ws || b > we)) {
      errors.startTime = `مرخصی ساعتی باید داخل ساعات کاری (${policy.workdayStart} تا ${policy.workdayEnd}) باشد`;
    }
  }
  if (draft.date) {
    if (!policy.workWeekdays.includes(pythonWeekday(draft.date))) {
      errors.date = "این تاریخ طبق الگوی کاری سازمان روز کاری نیست";
    }
    if (!policy.allowOnHoliday && holidays.includes(draft.date)) {
      errors.date = "ثبت مرخصی ساعتی در روز تعطیل طبق سیاست فعلی مجاز نیست";
    }
  }
  return errors;
}

export function findHourlyConflict(
  employeeId: number,
  draft: HourlyDraft,
  existing: ExistingInterval[],
  ignoreId?: number,
): ExistingInterval | null {
  for (const row of existing) {
    if (ignoreId != null && row.id === ignoreId) continue;
    if (row.employeeId !== employeeId) continue;
    if (!BLOCKING.has(row.status)) continue;
    if (!rangesOverlap(draft.date, draft.date, row.start, row.end)) continue;
    const kind = row.durationKind ?? "daily";
    if (kind === "daily") return row;
    if (row.startTime && row.endTime && timesOverlap(draft.startTime, draft.endTime, row.startTime, row.endTime)) {
      return row;
    }
  }
  return null;
}

export function findDailyConflict(
  employeeId: number,
  start: string,
  end: string,
  existing: ExistingInterval[],
  ignoreId?: number,
): ExistingInterval | null {
  for (const row of existing) {
    if (ignoreId != null && row.id === ignoreId) continue;
    if (row.employeeId !== employeeId) continue;
    if (!BLOCKING.has(row.status)) continue;
    if (rangesOverlap(start, end, row.start, row.end)) return row;
  }
  return null;
}
