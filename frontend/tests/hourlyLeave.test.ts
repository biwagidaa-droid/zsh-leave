import assert from "node:assert/strict";
import { test } from "node:test";
import {
  findDailyConflict, findHourlyConflict, formatDurationFa, minutesBetween, parseHm, timesOverlap, validateHourlyDraft,
  workingDaysFromMinutes, type ExistingInterval, type HourlyPolicy,
} from "../src/lib/hourlyLeave";

const policy: HourlyPolicy = {
  workdayStart: "08:00", workdayEnd: "16:00", allowOutsideWorkHours: false, allowOnHoliday: false,
  maxMinutesPerRequest: 240, workWeekdays: [0, 1, 2, 3, 4, 5, 6],
};

test("پارس و مدت", () => {
  assert.deepEqual(parseHm("09:30"), { h: 9, m: 30 });
  assert.equal(parseHm("24:00"), null);
  assert.equal(parseHm("9:30"), null);
  assert.equal(minutesBetween("10:00", "12:30"), 150);
  assert.equal(formatDurationFa(90), "1 ساعت و 30 دقیقه");
  assert.equal(formatDurationFa(60), "۱ ساعت");
  assert.equal(formatDurationFa(45), "45 دقیقه");
  assert.equal(formatDurationFa(0), "—");
  assert.equal(workingDaysFromMinutes(240, 480), "0.50");
});

test("اعتبارسنجی ساعت‌ها", () => {
  const ok = validateHourlyDraft({ date: "2026-10-27", startTime: "10:00", endTime: "12:00" }, policy, []);
  assert.deepEqual(ok, {});
  assert.ok(validateHourlyDraft({ date: "2026-10-27", startTime: "12:00", endTime: "10:00" }, policy, []).endTime);
  assert.ok(validateHourlyDraft({ date: "2026-10-27", startTime: "10:00", endTime: "10:00" }, policy, []).endTime);
  assert.ok(validateHourlyDraft({ date: "2026-10-27", startTime: "08:00", endTime: "14:00" }, policy, []).endTime, "سقف ۲۴۰ دقیقه");
  assert.ok(validateHourlyDraft({ date: "2026-10-27", startTime: "06:00", endTime: "07:00" }, policy, []).startTime, "خارج از ساعت کاری");
  assert.deepEqual(validateHourlyDraft({ date: "2026-10-27", startTime: "06:00", endTime: "07:00" }, { ...policy, allowOutsideWorkHours: true }, []), {});
  assert.ok(validateHourlyDraft({ date: "", startTime: "10:00", endTime: "11:00" }, policy, []).date);
});

test("تعطیل رسمی طبق سیاست", () => {
  const d = { date: "2026-10-27", startTime: "10:00", endTime: "11:00" };
  assert.ok(validateHourlyDraft(d, policy, ["2026-10-27"]).date);
  assert.deepEqual(validateHourlyDraft(d, { ...policy, allowOnHoliday: true }, ["2026-10-27"]), {});
});

test("هم‌پوشانی ساعتی: مرز مشترک تداخل نیست", () => {
  assert.equal(timesOverlap("10:00", "12:00", "12:00", "13:00"), false);
  assert.equal(timesOverlap("10:00", "12:00", "11:59", "13:00"), true);
});

test("تداخل با ساعتی، روزانه و وضعیت‌های غیرمسدودکننده", () => {
  const existing: ExistingInterval[] = [
    { id: 1, employeeId: 1, status: "APPROVED", start: "2026-10-27", end: "2026-10-27", durationKind: "hourly", startTime: "10:00", endTime: "12:00" },
    { id: 2, employeeId: 1, status: "REJECTED", start: "2026-10-28", end: "2026-10-28", durationKind: "daily" },
    { id: 3, employeeId: 2, status: "APPROVED", start: "2026-10-29", end: "2026-10-29", durationKind: "daily" },
    { id: 4, employeeId: 1, status: "PENDING", start: "2026-11-02", end: "2026-11-04" },
  ];
  assert.equal(findHourlyConflict(1, { date: "2026-10-27", startTime: "11:00", endTime: "13:00" }, existing)?.id, 1);
  assert.equal(findHourlyConflict(1, { date: "2026-10-27", startTime: "12:00", endTime: "13:00" }, existing), null);
  assert.equal(findHourlyConflict(1, { date: "2026-10-28", startTime: "10:00", endTime: "11:00" }, existing), null, "ردشده مسدود نمی‌کند");
  assert.equal(findHourlyConflict(1, { date: "2026-10-29", startTime: "10:00", endTime: "11:00" }, existing), null, "کارمند دیگر");
  assert.equal(findHourlyConflict(1, { date: "2026-11-03", startTime: "10:00", endTime: "11:00" }, existing)?.id, 4, "روزانه کل روز را می‌گیرد");
  assert.equal(findHourlyConflict(1, { date: "2026-10-27", startTime: "11:00", endTime: "13:00" }, existing, 1), null, "ignoreId");
  assert.equal(findDailyConflict(1, "2026-10-26", "2026-10-27", existing)?.id, 1);
  assert.equal(findDailyConflict(1, "2026-10-30", "2026-10-31", existing), null);
});
