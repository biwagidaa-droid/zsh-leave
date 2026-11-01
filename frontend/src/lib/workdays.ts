import { daysInRange, pythonWeekday } from "./jalali";

/** سقف طول بازه برای جلوگیری از حلقه‌های بسیار طولانی در مرورگر */
const MAX_RANGE_DAYS = 3660;

export function estimateWorkingDays(
  start: string,
  end: string,
  workWeekdays: number[],
  holidays: string[] = [],
): { days: number; estimated: true } {
  if (start > end) throw new Error("تاریخ شروع نباید بعد از تاریخ پایان باشد");
  if (!workWeekdays.length) throw new Error("الگوی روزهای کاری تعریف نشده است");
  const all = daysInRange(start, end, MAX_RANGE_DAYS);
  if (all.length > MAX_RANGE_DAYS) throw new Error("بازه انتخاب‌شده بیش از حد طولانی است");
  const hol = new Set(holidays);
  let n = 0;
  for (const d of all) {
    if (workWeekdays.includes(pythonWeekday(d)) && !hol.has(d)) n += 1;
  }
  return { days: n, estimated: true };
}
