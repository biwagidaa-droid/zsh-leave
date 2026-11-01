import assert from "node:assert/strict";
import { test } from "node:test";
import { computeSlices, formatPercent, formatValue, niceMax, slicePath } from "../src/components/charts";

test("computeSlices: درصدها جمع ۱۰۰ و مقادیر نامعتبر صفر", () => {
  const { slices, total } = computeSlices([{ label: "a", value: 1 }, { label: "b", value: 3 }, { label: "c", value: -5 }, { label: "d", value: NaN }]);
  assert.equal(total, 4);
  assert.equal(slices[0].percent, 25);
  assert.equal(slices[1].percent, 75);
  assert.equal(slices[2].value, 0);
  assert.ok(Math.abs(slices[3].end - Math.PI * 2) < 1e-9);
});

test("computeSlices: مجموع صفر", () => {
  const { slices, total } = computeSlices([{ label: "a", value: 0 }]);
  assert.equal(total, 0);
  assert.equal(slices[0].percent, 0);
});

test("slicePath: قطعه کامل، نیم‌دایره و قطعه صفر", () => {
  assert.equal(slicePath(100, 100, 80, 50, 0, 0), "");
  assert.match(slicePath(100, 100, 80, 0, 0, Math.PI * 2), /^M.*A.*A.*Z$/);
  assert.match(slicePath(100, 100, 80, 50, 0, Math.PI / 2), /^M.* A80 80 0 0 1 .* L.* A50 50 0 0 0 .* Z$/);
  assert.match(slicePath(100, 100, 80, 50, 0, 1.5 * Math.PI), / 0 1 1 /, "کمان بزرگ");
});

test("niceMax و قالب‌ها", () => {
  assert.equal(niceMax(0), 1);
  assert.equal(niceMax(3), 5);
  assert.equal(niceMax(7), 10);
  assert.equal(niceMax(120), 200);
  assert.equal(formatValue(2.456), "2.46");
  assert.equal(formatValue(3), "3");
  assert.equal(formatPercent(33.333), "33.3٪");
});
