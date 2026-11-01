import type { NotificationItem } from "../api/types";
import {
  KIND_CATEGORY, inferKind, shouldAlert, type NotifCategory, type NotifKind, type NotificationPrefs,
} from "./notificationPrefs";

/** نوع و دسته‌ی یک اعلان؛ اگر سرور نوع نفرستاده باشد از متن حدس زده می‌شود. */
export function kindOfItem(n: Pick<NotificationItem, "title" | "body" | "kind">): NotifKind {
  return inferKind(n.title, n.body, n.kind);
}

export function categoryOfItem(n: Pick<NotificationItem, "title" | "body" | "kind" | "category">): NotifCategory {
  const k = kindOfItem(n);
  const c = n.category;
  if (c === "request" || c === "approval" || c === "expiry" || c === "hr" || c === "system") return c;
  return KIND_CATEGORY[k];
}

export type NotifFilter = { category: NotifCategory | "all"; unreadOnly: boolean };

export function filterNotifications(items: NotificationItem[], f: NotifFilter): NotificationItem[] {
  return items.filter((n) => (!f.unreadOnly || !n.read) && (f.category === "all" || categoryOfItem(n) === f.category));
}

export function countByCategory(items: NotificationItem[]): Record<NotifCategory | "all", number> {
  const out: Record<NotifCategory | "all", number> = { all: items.length, request: 0, approval: 0, expiry: 0, hr: 0, system: 0 };
  for (const n of items) out[categoryOfItem(n)] += 1;
  return out;
}

export function unreadCount(items: NotificationItem[], prefs?: NotificationPrefs): number {
  return items.filter((n) => {
    if (n.read) return false;
    // نوعی که کاربر خاموش کرده، در شمارنده/Badge هم نمی‌آید (خود اعلان همچنان در مرکز اعلان می‌ماند)
    return prefs ? shouldAlert(prefs, kindOfItem(n)).visual : true;
  }).length;
}

export type AlertPlan = {
  /** اعلان‌های جدیدی که باید نمایش داده شوند (هرکدام فقط یک بار برای هر کاربر) */
  fresh: NotificationItem[];
  /** آیا برای این دسته باید صدا پخش شود (حداکثر یک بار برای کل دسته) */
  sound: boolean;
  /** شناسه‌هایی که باید به «دیده‌شده/پخش‌شده» اضافه شوند */
  markSeen: number[];
};

/**
 * تصمیم اعلان برای دسته‌ای از اعلان‌های دریافتی.
 * - اعلان خوانده‌شده یا قبلاً پخش‌شده تکرار نمی‌شود (جلوگیری از اعلان تکراری، حتی بین تب‌ها از طریق `seen` مشترک).
 * - `baseline=true` (اولین بارگذاری بدون سابقه) همه را بی‌صدا دیده‌شده می‌کند تا هجوم اعلان‌های قدیمی نداشته باشیم.
 * - اعلانی که با تنظیمات خاموش است، دیده‌شده ثبت می‌شود ولی نمایش/صدا ندارد.
 */
export function planAlerts(items: NotificationItem[], seen: ReadonlySet<number>, prefs: NotificationPrefs, baseline: boolean): AlertPlan {
  const fresh: NotificationItem[] = [];
  const markSeen: number[] = [];
  let sound = false;
  for (const n of items) {
    if (seen.has(n.id)) continue;
    markSeen.push(n.id);
    if (baseline || n.read) continue;
    const a = shouldAlert(prefs, kindOfItem(n));
    if (!a.visual) continue;
    fresh.push(n);
    if (a.sound) sound = true;
  }
  return { fresh, sound, markSeen };
}

/** مسیر مقصد اعلان؛ بدون requestId به مرکز اعلان برمی‌گردد (بدون ساخت مسیر ناموجود). */
export function targetOf(n: Pick<NotificationItem, "requestId">): string {
  return n.requestId ? `/requests/${n.requestId}` : "/notifications";
}
