export type ClientPolicy = {
  hourlyLeaveEnabled: boolean;
  workdayStart: string;
  workdayEnd: string;
  hourlyAllowOutsideWorkHours: boolean;
  hourlyAllowOnHoliday: boolean;
  hourlyMaxMinutesPerRequest: number;
  workdayMinutes: number;
  autoCancelEnabled: boolean;
  autoCancelDays: number | null;
  timezoneLabel: string;
};

export const DEFAULT_CLIENT_POLICY: ClientPolicy = {
  hourlyLeaveEnabled: true,
  workdayStart: "08:00",
  workdayEnd: "16:00",
  hourlyAllowOutsideWorkHours: false,
  hourlyAllowOnHoliday: false,
  hourlyMaxMinutesPerRequest: 480,
  workdayMinutes: 480,
  autoCancelEnabled: true,
  autoCancelDays: 3,
  timezoneLabel: "منطقه زمانی دستگاه کاربر (تقویم محلی)",
};

function asBool(v: unknown, fallback: boolean): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "number") {
    if (v === 1) return true;
    if (v === 0) return false;
  }
  if (typeof v === "string") {
    const t = v.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(t)) return true;
    if (["0", "false", "no", "n", "off"].includes(t)) return false;
  }
  return fallback;
}

function asHm(v: unknown, fallback: string): string {
  return typeof v === "string" && /^\d{2}:\d{2}$/.test(v) ? v : fallback;
}

function asInt(v: unknown, fallback: number): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
}

export type SettingLike = { key: string; value: unknown };

export function clientPolicyFromSettings(rows: SettingLike[]): ClientPolicy {
  const map = new Map(rows.map((s) => [s.key, s.value]));
  const enabled = asBool(map.get("workflow.auto_cancel_enabled"), true);
  const daysRaw = map.get("workflow.auto_cancel_pending_after_days");
  const days = asInt(daysRaw, 3);
  return {
    hourlyLeaveEnabled: asBool(map.get("policy.hourly_leave_enabled"), true),
    workdayStart: asHm(map.get("policy.workday_start"), "08:00"),
    workdayEnd: asHm(map.get("policy.workday_end"), "16:00"),
    hourlyAllowOutsideWorkHours: asBool(map.get("policy.hourly_allow_outside_work_hours"), false),
    hourlyAllowOnHoliday: asBool(map.get("policy.hourly_allow_on_holiday"), false),
    hourlyMaxMinutesPerRequest: asInt(map.get("policy.hourly_max_minutes_per_request"), 480),
    workdayMinutes: asInt(map.get("policy.workday_minutes"), 480),
    autoCancelEnabled: enabled,
    autoCancelDays: enabled ? days : null,
    timezoneLabel: "منطقه زمانی دستگاه کاربر (تقویم محلی)",
  };
}
