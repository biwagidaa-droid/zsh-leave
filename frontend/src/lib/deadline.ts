import type { LeaveRequest } from "../api/types";
import { AUTO_CANCELLED, AUTO_CANCEL_REASON_FA, datePart, decideAutoCancel } from "./autoCancel";
import { isOpenStatus } from "./roles";

export type DeadlineTone = "ok" | "warn" | "danger" | "muted";

export type DeadlineInfo = {
  kind: "waiting" | "overdue" | "auto_cancelled" | "no_policy";
  tone: DeadlineTone;
  /** برچسب کوتاه برای جدول و کارتابل */
  label: string;
  /** اولین روزی که درخواست منقضی محسوب می‌شود (ISO) */
  expiresAt?: string;
  /** آخرین روز معتبر برای تصمیم‌گیری (ISO) */
  lastValid?: string;
  remainingDays?: number;
  /** علت لغو خودکار (فقط وقتی لغو شده است) */
  reason?: string;
  cancelledAt?: string;
};

/** روزهای مانده تا انقضا که از آن به بعد رنگ هشدار می‌گیرد. */
export const DEADLINE_WARN_DAYS = 1;

/**
 * وضعیت مهلت تأیید یک درخواست؛ null یعنی موضوع مهلت برای این وضعیت بی‌معنی است
 * (مثلاً تأییدشده/ردشده/لغو دستی). تصمیم‌گیری به‌طور کامل با `decideAutoCancel` است تا
 * نمایش و منطق لغو یک منبع واحد داشته باشند.
 */
export function deadlineInfo(
  r: Pick<LeaveRequest, "status" | "createdAt" | "autoCancelPolicyDays" | "autoCancelledAt" | "autoCancelReason">,
  nowIso: string,
): DeadlineInfo | null {
  if (r.status === AUTO_CANCELLED) {
    return {
      kind: "auto_cancelled",
      tone: "muted",
      label: "لغو خودکار",
      reason: r.autoCancelReason || AUTO_CANCEL_REASON_FA,
      cancelledAt: r.autoCancelledAt,
    };
  }
  if (!isOpenStatus(r.status)) return null;
  const d = decideAutoCancel({ status: r.status, createdAt: r.createdAt, autoCancelPolicyDays: r.autoCancelPolicyDays }, datePart(nowIso));
  if (d.action === "skip") {
    return { kind: "no_policy", tone: "muted", label: "بدون مهلت خودکار" };
  }
  if (d.action === "cancel") {
    return {
      kind: "overdue", tone: "danger", label: "مهلت گذشته؛ در انتظار لغو خودکار",
      expiresAt: d.expiresAt, lastValid: d.lastValid, reason: d.reason,
    };
  }
  const n = d.remainingDays;
  return {
    kind: "waiting",
    tone: n <= DEADLINE_WARN_DAYS ? "warn" : "ok",
    label: n <= 0 ? "امروز آخرین روز مهلت است" : `${n} روز تا پایان مهلت`,
    expiresAt: d.expiresAt, lastValid: d.lastValid, remainingDays: n,
  };
}
