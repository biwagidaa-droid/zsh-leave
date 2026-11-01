import { addDaysIso } from "./jalali";
import { datePart } from "./autoCancel";

export type Spell = { start: string; end: string };

export type BradfordResult = {
  spells: number;
  days: number;
  score: number;
  merged: Spell[];
  note: string;
};

export const BRADFORD_NOTE =
  "ابزار تحلیلی کمکی است؛ مبنای تصمیم انضباطی، تشخیص سلامت یا ارزیابی قطعی عملکرد نیست.";

function dayDiffInclusive(start: string, end: string): number {
  const s = datePart(start);
  const e = datePart(end);
  if (e < s) return 0;
  let n = 1;
  let cur = s;
  while (cur < e) {
    cur = addDaysIso(cur, 1);
    n += 1;
    if (n > 20000) break;
  }
  return n;
}

function maxDate(a: string, b: string): string {
  return a >= b ? a : b;
}
function minDate(a: string, b: string): string {
  return a <= b ? a : b;
}

/**
 * BF = S² × D
 * دوره‌های هم‌پوشان یا پیوسته (روز بعد) یک دوره محسوب می‌شوند.
 * بازه به window برش می‌خورد. روزها تقویمی‌اند (شامل ابتدا و انتها).
 */
export function bradfordFactor(spells: Spell[], windowStart: string, windowEnd: string): BradfordResult {
  const ws = datePart(windowStart);
  const we = datePart(windowEnd);
  if (ws > we) throw new Error("بازه نامعتبر");
  const clipped: Spell[] = [];
  for (const sp of spells) {
    const s = datePart(sp.start);
    const e = datePart(sp.end);
    if (s > e) continue;
    if (s > we || e < ws) continue;
    clipped.push({ start: maxDate(s, ws), end: minDate(e, we) });
  }
  clipped.sort((a, b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end));
  const merged: Spell[] = [];
  for (const sp of clipped) {
    const last = merged[merged.length - 1];
    if (last && sp.start <= addDaysIso(last.end, 1)) {
      last.end = maxDate(last.end, sp.end);
    } else {
      merged.push({ ...sp });
    }
  }
  const S = merged.length;
  const D = merged.reduce((sum, m) => sum + dayDiffInclusive(m.start, m.end), 0);
  return { spells: S, days: D, score: S * S * D, merged, note: BRADFORD_NOTE };
}

export type BradfordLevel = "normal" | "attention" | "warn" | "serious" | "review";

export type BradfordThresholds = {
  attention: number;
  warn: number;
  serious: number;
  review: number;
};

export const DEFAULT_BRADFORD_THRESHOLDS: BradfordThresholds = {
  attention: 50,
  warn: 200,
  serious: 500,
  review: 1000,
};

export const BRADFORD_LEVEL_LABEL: Record<BradfordLevel, string> = {
  normal: "عادی",
  attention: "نیازمند توجه",
  warn: "هشدار",
  serious: "هشدار جدی",
  review: "نیازمند بررسی HR",
};

export function bradfordLevel(score: number, t: BradfordThresholds = DEFAULT_BRADFORD_THRESHOLDS): BradfordLevel {
  if (score >= t.review) return "review";
  if (score >= t.serious) return "serious";
  if (score >= t.warn) return "warn";
  if (score >= t.attention) return "attention";
  return "normal";
}

export type RangePreset = "30" | "90" | "180" | "365" | "custom";

export function windowForPreset(preset: RangePreset, today: string, customFrom?: string, customTo?: string): { from: string; to: string } {
  if (preset === "custom" && customFrom && customTo) {
    return { from: datePart(customFrom), to: datePart(customTo) };
  }
  const days = preset === "custom" ? 90 : Number(preset);
  return { from: addDaysIso(datePart(today), -(days - 1)), to: datePart(today) };
}

export function previousWindow(from: string, to: string): { from: string; to: string } {
  const len = dayDiffInclusive(from, to);
  const prevTo = addDaysIso(datePart(from), -1);
  const prevFrom = addDaysIso(prevTo, -(len - 1));
  return { from: prevFrom, to: prevTo };
}

export function hourlyMinutesAsDays(minutes: number, minutesPerDay: number): number | null {
  if (minutesPerDay <= 0 || minutes <= 0) return null;
  return minutes / minutesPerDay;
}
