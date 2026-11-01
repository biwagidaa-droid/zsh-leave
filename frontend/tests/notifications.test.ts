import assert from "node:assert/strict";
import { test } from "node:test";
import type { NotificationItem } from "../src/api/types";
import {
  countByCategory, filterNotifications, kindOfItem, planAlerts, targetOf, unreadCount,
} from "../src/lib/notificationEngine";
import { defaultNotificationPrefs, parseNotificationPrefs, shouldAlert } from "../src/lib/notificationPrefs";

const n = (id: number, over: Partial<NotificationItem> = {}): NotificationItem => (
  { id, title: "درخواست مرخصی", body: "متن", read: false, createdAt: "2026-11-01", ...over }
);

test("پیش‌فرض‌ها و پارس تنظیمات خراب", () => {
  const d = defaultNotificationPrefs();
  assert.equal(d.master, "on_sound");
  assert.equal(parseNotificationPrefs("خراب").master, "on_sound");
  assert.equal(parseNotificationPrefs({ master: "off", volume: 5, soundId: "x" }).volume, d.volume, "شدت خارج از بازه رد می‌شود");
  assert.equal(parseNotificationPrefs({ master: "off" }).master, "off");
});

test("حالت‌های روشن/بی‌صدا/خاموش", () => {
  const p = defaultNotificationPrefs();
  assert.deepEqual(shouldAlert(p, "approved"), { visual: true, sound: true });
  assert.deepEqual(shouldAlert({ ...p, master: "on_silent" }, "approved"), { visual: true, sound: false });
  assert.deepEqual(shouldAlert({ ...p, master: "off" }, "approved"), { visual: false, sound: false });
  assert.deepEqual(shouldAlert({ ...p, kinds: { ...p.kinds, approved: false } }, "approved"), { visual: false, sound: false });
});

test("planAlerts: اولین بارگذاری بی‌صدا، سپس فقط جدیدها، بدون تکرار", () => {
  const p = defaultNotificationPrefs();
  const first = planAlerts([n(1), n(2)], new Set(), p, true);
  assert.equal(first.fresh.length, 0);
  assert.deepEqual(first.markSeen, [1, 2]);
  const second = planAlerts([n(1), n(2), n(3)], new Set([1, 2]), p, false);
  assert.deepEqual(second.fresh.map((x) => x.id), [3]);
  assert.equal(second.sound, true);
  const again = planAlerts([n(1), n(2), n(3)], new Set([1, 2, 3]), p, false);
  assert.equal(again.fresh.length, 0, "اعلان تکراری ندارد");
});

test("planAlerts: خوانده‌شده، بی‌صدا و نوع خاموش", () => {
  const p = defaultNotificationPrefs();
  assert.equal(planAlerts([n(5, { read: true })], new Set(), p, false).fresh.length, 0);
  const silent = planAlerts([n(6)], new Set(), { ...p, master: "on_silent" }, false);
  assert.equal(silent.fresh.length, 1);
  assert.equal(silent.sound, false);
  const muted = planAlerts([n(7, { kind: "approved" })], new Set(), { ...p, kinds: { ...p.kinds, approved: false } }, false);
  assert.equal(muted.fresh.length, 0);
  assert.deepEqual(muted.markSeen, [7], "خاموش‌شده هم دیده‌شده ثبت می‌شود تا بعداً با روشن‌کردن یکدفعه نیاید");
});

test("دسته‌بندی، فیلتر و شمارنده", () => {
  const items = [
    n(1, { kind: "approved" }), n(2, { kind: "auto_cancelled", read: true }), n(3, { kind: "expiry_soon" }), n(4, { title: "مرخصی ساعتی", body: "ثبت شد" }),
  ];
  assert.equal(kindOfItem(items[3]), "hourly_created");
  const c = countByCategory(items);
  assert.equal(c.all, 4);
  assert.equal(c.approval, 2);
  assert.equal(c.expiry, 1);
  assert.equal(filterNotifications(items, { category: "approval", unreadOnly: true }).length, 1);
  assert.equal(unreadCount(items), 3);
  assert.equal(unreadCount(items, { ...defaultNotificationPrefs(), master: "off" }), 0);
  assert.equal(targetOf({ requestId: 12 }), "/requests/12");
  assert.equal(targetOf({}), "/notifications");
});
