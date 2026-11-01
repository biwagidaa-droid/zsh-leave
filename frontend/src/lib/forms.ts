import { normalizeNumberInput } from "./jalali";

/** کلیدهای snake_case خطاهای سرور را به camelCase تبدیل می‌کند تا با نام فیلدهای فرم یکی شود. */
export function camelFields(fields: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(fields)) {
    out[k.replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase())] = v;
  }
  return out;
}

/** عدد مثبت از ورودی کاربر (ارقام فارسی هم پذیرفته می‌شود)؛ در صورت نامعتبر بودن null. */
export function positiveNumber(text: string): number | null {
  const norm = normalizeNumberInput(text);
  if (!norm) return null;
  const n = Number(norm);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** عدد (مثبت یا منفی، غیر صفر) از ورودی کاربر یا null. */
export function nonZeroNumber(text: string): number | null {
  const norm = normalizeNumberInput(text);
  if (!norm) return null;
  const n = Number(norm);
  return Number.isFinite(n) && n !== 0 ? n : null;
}
