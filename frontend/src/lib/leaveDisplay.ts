import type { LeaveRequest } from "../api/types";
import { formatJalaliSafe } from "./jalali";
import { formatDurationFa } from "./hourlyLeave";

export function durationKindOf(r: { durationKind?: string }): "daily" | "hourly" {
  return r.durationKind === "hourly" ? "hourly" : "daily";
}

export function durationKindLabel(kind: string | undefined): string {
  return kind === "hourly" ? "ساعتی" : "روزانه";
}

export function formatRequestRange(
  r: Pick<LeaveRequest, "start" | "end" | "durationKind" | "startTime" | "endTime">,
  withMonthName = false,
): string {
  if (durationKindOf(r) === "hourly") {
    const t = r.startTime && r.endTime ? ` ${r.startTime}–${r.endTime}` : "";
    return `${formatJalaliSafe(r.start, withMonthName)}${t}`;
  }
  if (r.start === r.end) return formatJalaliSafe(r.start, withMonthName);
  return `${formatJalaliSafe(r.start, withMonthName)} — ${formatJalaliSafe(r.end, withMonthName)}`;
}

export function formatRequestDuration(r: Pick<LeaveRequest, "workingDays" | "durationKind" | "durationMinutes">): string {
  if (durationKindOf(r) === "hourly" && r.durationMinutes != null) {
    return formatDurationFa(r.durationMinutes);
  }
  return `${r.workingDays} روز`;
}
