import type { Holiday } from "../api/types";
import { fromGregorian, isoToG, jalaliToIsoSafe } from "./jalali";

/** سال شمسی یک تاریخ ISO؛ برای تاریخ نامعتبر null. */
export function jalaliYearOfIso(iso: string): number | null {
  try {
    return fromGregorian(isoToG(iso)).jy;
  } catch {
    return null;
  }
}

/** تاریخ‌های ISO تعطیلات برای یک سال شمسی (تعطیلات سالانه + مختص همان سال). */
export function holidayIsosForYear(holidays: Holiday[], jy: number): string[] {
  const out: string[] = [];
  for (const h of holidays) {
    if (h.jalaliYear != null && h.jalaliYear !== jy) continue;
    const iso = jalaliToIsoSafe(jy, h.jalaliMonth, h.jalaliDay);
    if (iso) out.push(iso);
  }
  return out;
}

/** تعطیلات یک بازه که ممکن است چند سال شمسی را پوشش دهد. */
export function holidayIsosForRange(holidays: Holiday[], startIso: string, endIso: string): string[] {
  const a = jalaliYearOfIso(startIso);
  const b = jalaliYearOfIso(endIso);
  if (a == null || b == null) return [];
  const years = new Set<number>();
  for (let y = Math.min(a, b); y <= Math.max(a, b); y += 1) years.add(y);
  const all = new Set<string>();
  for (const y of years) for (const iso of holidayIsosForYear(holidays, y)) all.add(iso);
  return [...all];
}
