import assert from "node:assert/strict";
import { test } from "node:test";
import {
  AUTO_CANCELLED, calendarDayDiff, decideAutoCancel, expiryDate, isPastDeadline, lastValidDate, parseAutoCancelDays,
  remainingCalendarDays, snapshotAutoCancelDays,
} from "../src/lib/autoCancel";
import { deadlineInfo } from "../src/lib/deadline";

test("تاریخ انقضا و آخرین روز معتبر", () => {
  assert.equal(expiryDate("2026-10-28", 3), "2026-10-31");
  assert.equal(lastValidDate("2026-10-28", 3), "2026-10-30");
});

test("مرز مهلت: روز انقضا منقضی است، روز قبل هنوز معتبر", () => {
  assert.equal(isPastDeadline("2026-10-28", 3, "2026-10-30"), false);
  assert.equal(isPastDeadline("2026-10-28", 3, "2026-10-31"), true);
  assert.equal(remainingCalendarDays("2026-10-28", 3, "2026-10-30"), 0);
  assert.equal(remainingCalendarDays("2026-10-28", 3, "2026-10-29"), 1);
});

test("N غیرفعال یا نامعتبر هیچ‌وقت منقضی نمی‌شود", () => {
  assert.equal(isPastDeadline("2020-01-01", 0, "2026-10-31"), false);
  assert.equal(snapshotAutoCancelDays(false, 3), null);
  assert.equal(snapshotAutoCancelDays(true, 0), null);
  assert.equal(snapshotAutoCancelDays(true, 2.5), null);
  assert.equal(snapshotAutoCancelDays(true, 4), 4);
  assert.equal(parseAutoCancelDays("5"), 5);
  assert.equal(parseAutoCancelDays("-1"), null);
  assert.equal(parseAutoCancelDays(""), null);
});

test("فقط وضعیت باز پردازش می‌شود؛ تأییدشده/ردشده/لغوشده دوباره لغو نمی‌شوند", () => {
  for (const status of ["APPROVED", "REJECTED", "CANCELLED", AUTO_CANCELLED, "WITHDRAWAL_PENDING"]) {
    const d = decideAutoCancel({ status, createdAt: "2020-01-01", autoCancelPolicyDays: 1 }, "2026-10-31");
    assert.equal(d.action, "skip", status);
  }
  const d = decideAutoCancel({ status: "PENDING", createdAt: "2020-01-01", autoCancelPolicyDays: 1 }, "2026-10-31");
  assert.equal(d.action, "cancel");
});

test("درخواست بدون N ثبت‌شده (سیاست غیرفعال هنگام ثبت) skip می‌شود", () => {
  const d = decideAutoCancel({ status: "PENDING", createdAt: "2020-01-01", autoCancelPolicyDays: null }, "2026-10-31");
  assert.equal(d.action, "skip");
});

test("calendarDayDiff علامت‌دار است", () => {
  assert.equal(calendarDayDiff("2026-10-28", "2026-10-31"), 3);
  assert.equal(calendarDayDiff("2026-10-31", "2026-10-28"), -3);
});

test("deadlineInfo: انتظار، هشدار، گذشته، لغو خودکار، نامرتبط", () => {
  const base = { createdAt: "2026-10-28", autoCancelPolicyDays: 3 };
  const wait = deadlineInfo({ ...base, status: "PENDING" }, "2026-10-28");
  assert.equal(wait?.kind, "waiting");
  assert.equal(wait?.tone, "ok");
  const warn = deadlineInfo({ ...base, status: "PENDING" }, "2026-10-30");
  assert.equal(warn?.tone, "warn");
  assert.match(warn?.label ?? "", /آخرین روز/);
  assert.equal(deadlineInfo({ ...base, status: "PENDING" }, "2026-11-02")?.kind, "overdue");
  const auto = deadlineInfo({ ...base, status: AUTO_CANCELLED, autoCancelReason: "علت", autoCancelledAt: "2026-10-31" }, "2026-11-01");
  assert.equal(auto?.kind, "auto_cancelled");
  assert.equal(auto?.reason, "علت");
  assert.equal(deadlineInfo({ ...base, status: "APPROVED" }, "2026-11-01"), null);
  assert.equal(deadlineInfo({ createdAt: "2026-10-28", autoCancelPolicyDays: null, status: "PENDING" }, "2026-11-01")?.kind, "no_policy");
});
