import { addDaysIso } from "./jalali";

/** وضعیت اختصاصی لغو به‌خاطر سپری شدن مهلت تأیید. */
export const AUTO_CANCELLED = "AUTO_CANCELLED";

export const AUTO_CANCEL_ELIGIBLE = ["PENDING", "ESCALATED"] as const;

export function datePart(iso: string): string {
  return iso.slice(0, 10);
}

/** تاریخ انقضا (اولین روزی که درخواست منقضی محسوب می‌شود) = روز ثبت + N روز تقویمی. */
export function expiryDate(createdAt: string, policyDays: number): string {
  return addDaysIso(datePart(createdAt), policyDays);
}

/** آخرین روز معتبر برای تصمیم‌گیری (شامل خود آن روز). */
export function lastValidDate(createdAt: string, policyDays: number): string {
  return addDaysIso(datePart(createdAt), policyDays - 1);
}

/**
 * اختلاف روز تقویمی بین دو تاریخ ISO (فقط بخش تاریخ).
 * مقدار مثبت یعنی `to` بعد از `from` است.
 */
export function calendarDayDiff(fromIso: string, toIso: string): number {
  const from = datePart(fromIso);
  const to = datePart(toIso);
  let n = 0;
  let cur = from;
  if (to >= from) {
    while (cur < to) {
      cur = addDaysIso(cur, 1);
      n += 1;
      if (n > 20000) break;
    }
    return n;
  }
  while (cur > to) {
    cur = addDaysIso(cur, -1);
    n -= 1;
    if (n < -20000) break;
  }
  return n;
}

export function isPastDeadline(createdAt: string, policyDays: number, nowIso: string): boolean {
  if (policyDays <= 0) return false;
  return datePart(nowIso) >= expiryDate(createdAt, policyDays);
}

/** روزهای باقی‌مانده تا انقضا؛ ۰ یعنی امروز آخرین روز معتبر است؛ منفی یعنی منقضی. */
export function remainingCalendarDays(createdAt: string, policyDays: number, nowIso: string): number {
  return calendarDayDiff(datePart(nowIso), lastValidDate(createdAt, policyDays));
}

export type AutoCancelSnapshot = number | null;

/**
 * مقدار N که روی درخواست قفل می‌شود.
 * اگر سیاست هنگام ثبت غیرفعال باشد، null ذخیره می‌شود و تغییر بعدی N این درخواست را عوض نمی‌کند.
 */
export function snapshotAutoCancelDays(enabled: boolean, days: number): AutoCancelSnapshot {
  if (!enabled) return null;
  if (!Number.isFinite(days) || days < 1 || !Number.isInteger(days)) return null;
  return days;
}

export function parseAutoCancelDays(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(String(value).trim());
  if (!Number.isFinite(n) || !Number.isInteger(n) || n < 1) return null;
  return n;
}

export type AutoCancelInput = {
  status: string;
  createdAt: string;
  autoCancelPolicyDays?: AutoCancelSnapshot;
};

export type AutoCancelDecision =
  | { action: "skip"; reason: string }
  | { action: "wait"; expiresAt: string; lastValid: string; remainingDays: number }
  | { action: "cancel"; expiresAt: string; lastValid: string; reason: string };

/**
 * تصمیم لغو خودکار فقط بر اساس وضعیت فعلی و N ذخیره‌شده روی همان درخواست.
 * سیاست جاری سامانه روی درخواست‌های قبلی اثر نمی‌گذارد.
 */
export function decideAutoCancel(req: AutoCancelInput, nowIso: string): AutoCancelDecision {
  if (!(AUTO_CANCEL_ELIGIBLE as readonly string[]).includes(req.status)) {
    return { action: "skip", reason: "وضعیت مشمول لغو خودکار نیست" };
  }
  const n = req.autoCancelPolicyDays;
  if (n == null) {
    return { action: "skip", reason: "در زمان ثبت، لغو خودکار برای این درخواست فعال نبوده است" };
  }
  const expiresAt = expiryDate(req.createdAt, n);
  const lastValid = lastValidDate(req.createdAt, n);
  if (isPastDeadline(req.createdAt, n, nowIso)) {
    return {
      action: "cancel",
      expiresAt,
      lastValid,
      reason: `مهلت ${n} روز تقویمی برای تأیید به پایان رسید`,
    };
  }
  return {
    action: "wait",
    expiresAt,
    lastValid,
    remainingDays: remainingCalendarDays(req.createdAt, n, nowIso),
  };
}

export const AUTO_CANCEL_REASON_FA = "لغو خودکار به‌خاطر سپری شدن مهلت تأیید";
