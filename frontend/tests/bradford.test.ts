import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULT_BRADFORD_THRESHOLDS, bradfordFactor, bradfordLevel, previousWindow, windowForPreset } from "../src/lib/bradford";
import {
  DEFAULT_BRADFORD_CONFIG, DEFAULT_WORK_WEEKDAYS, analyzeEmployee, bradfordConfigFromSettings, levelCounts, monthWindows,
  validThresholds, validWindow, type AbsenceRecord,
} from "../src/lib/bradfordAnalysis";

// امروز آزمون: یکشنبه ۲۰۲۶-۱۱-۰۱. روزهای کاری پیش‌فرض: شنبه تا چهارشنبه (پنجشنبه/جمعه تعطیل).
const TODAY = "2026-11-01";
const WIN = { from: "2026-10-01", to: TODAY };
const ctx = { workWeekdays: DEFAULT_WORK_WEEKDAYS, holidays: [] as string[] };
const sick = (start: string, end = start, extra: Partial<AbsenceRecord> = {}): AbsenceRecord => (
  { employeeId: 1, status: "APPROVED", type: "sick", start, end, ...extra }
);

test("فرمول و سطح‌ها", () => {
  const r = bradfordFactor([{ start: "2026-10-01", end: "2026-10-02" }, { start: "2026-10-10", end: "2026-10-10" }], "2026-10-01", "2026-10-31");
  assert.equal(r.spells, 2);
  assert.equal(r.days, 3);
  assert.equal(r.score, 12);
  assert.equal(bradfordLevel(0), "normal");
  assert.equal(bradfordLevel(49), "normal");
  assert.equal(bradfordLevel(50), "attention");
  assert.equal(bradfordLevel(200), "warn");
  assert.equal(bradfordLevel(500), "serious");
  assert.equal(bradfordLevel(999), "serious");
  assert.equal(bradfordLevel(1000), "review");
  assert.equal(bradfordLevel(150, { ...DEFAULT_BRADFORD_THRESHOLDS, warn: 100 }), "warn", "آستانه قابل تنظیم");
});

test("بازه‌ها", () => {
  assert.deepEqual(windowForPreset("30", TODAY), { from: "2026-10-03", to: TODAY });
  assert.deepEqual(windowForPreset("custom", TODAY, "2026-01-01", "2026-02-01"), { from: "2026-01-01", to: "2026-02-01" });
  assert.deepEqual(previousWindow("2026-10-03", TODAY), { from: "2026-09-03", to: "2026-10-02" });
  assert.equal(validWindow("2026-10-05", "2026-10-01"), false);
  assert.equal(validWindow("2020-01-01", "2026-10-01"), false, "بیش از سقف");
});

test("غیبت پیوسته یک دوره است؛ جمعه/پنجشنبه تعطیل دوره را نمی‌شکند", () => {
  // سه‌شنبه ۲۷ و چهارشنبه ۲۸، سپس شنبه ۳۱ (پنجشنبه و جمعه روز کاری نیستند)
  const r = analyzeEmployee([sick("2026-10-27", "2026-10-28"), sick("2026-10-31")], WIN, ctx, DEFAULT_BRADFORD_CONFIG, TODAY);
  assert.equal(r.spells, 1);
  assert.equal(r.days, 3);
  assert.equal(r.score, 3);
});

test("وجود روز کاری میانی دوره‌ها را جدا می‌کند", () => {
  // دوشنبه ۲۶ و شنبه ۳۱ با روزهای کاری سه‌شنبه و چهارشنبه در میان
  const r = analyzeEmployee([sick("2026-10-26"), sick("2026-10-31")], WIN, ctx, DEFAULT_BRADFORD_CONFIG, TODAY);
  assert.equal(r.spells, 2);
  assert.equal(r.days, 2);
  assert.equal(r.score, 8);
});

test("تعطیل رسمی روز کاری حساب نمی‌شود و دوره را پیوسته نگه می‌دارد", () => {
  const withHoliday = { workWeekdays: DEFAULT_WORK_WEEKDAYS, holidays: ["2026-10-26"] };
  const r = analyzeEmployee([sick("2026-10-25"), sick("2026-10-27")], WIN, withHoliday, DEFAULT_BRADFORD_CONFIG, TODAY);
  assert.equal(r.spells, 1);
  assert.equal(r.days, 2);
});

test("مرخصی برنامه‌ریزی‌شده/غیرمشمول، غیرتأییدشده و آینده شمرده نمی‌شود", () => {
  const recs: AbsenceRecord[] = [
    { employeeId: 1, status: "APPROVED", type: "annual", start: "2026-10-26", end: "2026-10-27" },
    sick("2026-10-26", "2026-10-26", { status: "PENDING" }),
    sick("2026-10-26", "2026-10-26", { status: "REJECTED" }),
    sick("2026-10-26", "2026-10-26", { status: "AUTO_CANCELLED" }),
    sick("2026-11-02", "2026-11-03"),
  ];
  const r = analyzeEmployee(recs, WIN, ctx, DEFAULT_BRADFORD_CONFIG, TODAY);
  assert.equal(r.spells, 0);
  assert.equal(r.score, 0);
  assert.equal(r.level, "normal");
});

test("غیبت خارج از بازه حذف و غیبت مرزی برش می‌خورد", () => {
  // پنجره از شنبه ۲۰۲۶-۱۰-۰۳ شروع می‌شود (۱ و ۲ مهر/اکتبر پنجشنبه و جمعه‌اند)
  const w = { from: "2026-10-03", to: TODAY };
  const r = analyzeEmployee([sick("2026-09-20", "2026-09-30"), sick("2026-10-01", "2026-10-03")], w, ctx, DEFAULT_BRADFORD_CONFIG, TODAY);
  assert.equal(r.spells, 1);
  assert.equal(r.days, 1);
});

test("مرخصی ساعتی: پیش‌فرض نادیده؛ با سیاست تبدیل کسری از روز؛ هرگز روز کامل نیست", () => {
  const hourly = sick("2026-10-27", "2026-10-27", { durationKind: "hourly", durationMinutes: 240 });
  assert.equal(analyzeEmployee([hourly], WIN, ctx, DEFAULT_BRADFORD_CONFIG, TODAY).spells, 0);
  const cfg = { ...DEFAULT_BRADFORD_CONFIG, includeHourly: true, hourlyMinutesPerDay: 480 };
  const r = analyzeEmployee([hourly], WIN, ctx, cfg, TODAY);
  assert.equal(r.spells, 1);
  assert.equal(r.days, 0.5);
  assert.equal(r.score, 0.5);
  const full = analyzeEmployee([hourly, sick("2026-10-27")], WIN, ctx, cfg, TODAY);
  assert.equal(full.days, 1, "روز کامل بر ساعتی غالب است و دوبار شمرده نمی‌شود");
});

test("داده ناقص امتیاز نمی‌سازد", () => {
  const bad = analyzeEmployee([sick("2026-10-28", "2026-10-26"), sick("نامعتبر")], WIN, ctx, DEFAULT_BRADFORD_CONFIG, TODAY);
  assert.equal(bad.spells, 0);
  assert.equal(bad.score, 0);
  assert.equal(bad.skippedInvalid, 2);
  assert.throws(() => analyzeEmployee([], { from: "2026-10-05", to: "2026-10-01" }, ctx, DEFAULT_BRADFORD_CONFIG, TODAY));
  const noMinutes = analyzeEmployee([sick("2026-10-27", "2026-10-27", { durationKind: "hourly" })], WIN, ctx, { ...DEFAULT_BRADFORD_CONFIG, includeHourly: true }, TODAY);
  assert.equal(noMinutes.skippedInvalid, 1);
});

test("تنظیمات: پیش‌فرض، آستانه نامعتبر، انواع مشمول", () => {
  assert.equal(bradfordConfigFromSettings(null).includeTypes[0], "sick");
  const cfg = bradfordConfigFromSettings([
    { key: "bradford.include_types", value: "sick, unpaid" },
    { key: "bradford.threshold_warn", value: 300 },
    { key: "bradford.include_hourly", value: "true" },
  ]);
  assert.deepEqual(cfg.includeTypes, ["sick", "unpaid"]);
  assert.equal(cfg.thresholds.warn, 300);
  assert.equal(cfg.includeHourly, true);
  const broken = bradfordConfigFromSettings([{ key: "bradford.threshold_warn", value: 10 }]);
  assert.deepEqual(broken.thresholds, DEFAULT_BRADFORD_THRESHOLDS, "ترتیب نامعتبر → پیش‌فرض");
  assert.equal(validThresholds({ attention: 1, warn: 2, serious: 3, review: 3 }), false);
});

test("شمارش سطوح و پنجره‌های ماهانه", () => {
  assert.deepEqual(levelCounts([{ level: "normal" }, { level: "review" }, { level: "normal" }]), { normal: 2, attention: 0, warn: 0, serious: 0, review: 1 });
  const m = monthWindows("2026-10-01", "2026-11-01");
  assert.ok(m.length >= 2 && m.length <= 3);
  assert.equal(m[0].from, "2026-10-01");
  assert.equal(m[m.length - 1].to, "2026-11-01");
  assert.deepEqual(monthWindows("2026-11-01", "2026-10-01"), []);
});
