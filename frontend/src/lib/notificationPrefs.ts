export type NotifMaster = "on_sound" | "on_silent" | "off";

export type NotifKind =
  | "request_created"
  | "request_sent_manager"
  | "hourly_created"
  | "approved"
  | "rejected"
  | "cancelled"
  | "auto_cancelled"
  | "pending"
  | "expiry_soon"
  | "hr_admin";

export type NotifCategory = "request" | "approval" | "expiry" | "hr" | "system";

export type SoundId = "chime" | "soft" | "alert";

export type NotificationPrefs = {
  master: NotifMaster;
  volume: number;
  soundId: SoundId;
  desktop: boolean;
  kinds: Record<NotifKind, boolean>;
};

export const NOTIF_KIND_LABEL: Record<NotifKind, string> = {
  request_created: "ثبت درخواست مرخصی جدید",
  request_sent_manager: "ارسال درخواست برای مدیر",
  hourly_created: "ثبت مرخصی ساعتی",
  approved: "تأیید درخواست",
  rejected: "رد درخواست",
  cancelled: "لغو درخواست",
  auto_cancelled: "لغو خودکار درخواست",
  pending: "درخواست در انتظار تأیید",
  expiry_soon: "نزدیک شدن به پایان مهلت تأیید",
  hr_admin: "اعلان‌های مدیریتی و HR",
};

export const NOTIF_CATEGORY_LABEL: Record<NotifCategory, string> = {
  request: "درخواست",
  approval: "تصمیم",
  expiry: "مهلت",
  hr: "منابع انسانی",
  system: "سامانه",
};

export const KIND_CATEGORY: Record<NotifKind, NotifCategory> = {
  request_created: "request",
  request_sent_manager: "request",
  hourly_created: "request",
  approved: "approval",
  rejected: "approval",
  cancelled: "approval",
  auto_cancelled: "approval",
  pending: "expiry",
  expiry_soon: "expiry",
  hr_admin: "hr",
};

const ALL_KINDS: NotifKind[] = [
  "request_created", "request_sent_manager", "hourly_created", "approved", "rejected",
  "cancelled", "auto_cancelled", "pending", "expiry_soon", "hr_admin",
];

export function defaultNotificationPrefs(): NotificationPrefs {
  const kinds = {} as Record<NotifKind, boolean>;
  for (const k of ALL_KINDS) kinds[k] = true;
  return { master: "on_sound", volume: 0.45, soundId: "chime", desktop: false, kinds };
}

export function parseNotificationPrefs(raw: unknown): NotificationPrefs {
  const base = defaultNotificationPrefs();
  if (!raw || typeof raw !== "object") return base;
  const o = raw as Partial<NotificationPrefs> & { kinds?: Partial<Record<NotifKind, boolean>> };
  if (o.master === "on_sound" || o.master === "on_silent" || o.master === "off") base.master = o.master;
  if (typeof o.volume === "number" && o.volume >= 0 && o.volume <= 1) base.volume = o.volume;
  if (o.soundId === "chime" || o.soundId === "soft" || o.soundId === "alert") base.soundId = o.soundId;
  if (typeof o.desktop === "boolean") base.desktop = o.desktop;
  if (o.kinds && typeof o.kinds === "object") {
    for (const k of ALL_KINDS) {
      if (typeof o.kinds[k] === "boolean") base.kinds[k] = o.kinds[k]!;
    }
  }
  return base;
}

export function prefsStorageKey(userId: number): string {
  return `zsh-leave-notif-prefs-u${userId}`;
}

export function playedIdsStorageKey(userId: number): string {
  return `zsh-leave-notif-played-u${userId}`;
}

export function loadPlayedIds(userId: number): Set<number> {
  try {
    const raw = localStorage.getItem(playedIdsStorageKey(userId));
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is number => typeof x === "number"));
  } catch {
    return new Set();
  }
}

export function savePlayedIds(userId: number, ids: Set<number>): void {
  const trimmed = [...ids].slice(-400);
  try {
    localStorage.setItem(playedIdsStorageKey(userId), JSON.stringify(trimmed));
  } catch { /* ظرفیت ذخیره */ }
}

export function inferKind(title: string, body: string, explicit?: string): NotifKind {
  if (explicit && (ALL_KINDS as string[]).includes(explicit)) return explicit as NotifKind;
  const t = `${title} ${body}`;
  if (t.includes("ساعتی")) return "hourly_created";
  if (t.includes("لغو خودکار") || t.includes("AUTO_CANCELLED")) return "auto_cancelled";
  if (t.includes("مهلت")) return "expiry_soon";
  if (t.includes("تأیید")) return "approved";
  if (t.includes("رد")) return "rejected";
  if (t.includes("لغو")) return "cancelled";
  if (t.includes("در انتظار")) return "pending";
  if (t.includes("مدیر")) return "request_sent_manager";
  return "request_created";
}

export function shouldAlert(prefs: NotificationPrefs, kind: NotifKind): { visual: boolean; sound: boolean } {
  if (prefs.master === "off") return { visual: false, sound: false };
  if (!prefs.kinds[kind]) return { visual: false, sound: false };
  return { visual: true, sound: prefs.master === "on_sound" };
}

export const SOUND_LABEL: Record<SoundId, string> = {
  chime: "زنگ کوتاه",
  soft: "ملایم",
  alert: "هشدار",
};

export const MASTER_LABEL: Record<NotifMaster, string> = {
  on_sound: "روشن با صدا",
  on_silent: "روشن بی‌صدا",
  off: "خاموش",
};

export const ALL_NOTIF_KINDS: readonly NotifKind[] = ALL_KINDS;

export function savePrefs(userId: number, prefs: NotificationPrefs): void {
  try {
    localStorage.setItem(prefsStorageKey(userId), JSON.stringify(prefs));
  } catch { /* ظرفیت یا حالت خصوصی */ }
}

export function loadPrefs(userId: number): NotificationPrefs {
  try {
    const raw = localStorage.getItem(prefsStorageKey(userId));
    return parseNotificationPrefs(raw ? (JSON.parse(raw) as unknown) : null);
  } catch {
    return defaultNotificationPrefs();
  }
}

/** آیا برای این کاربر پیش‌تر مجموعه‌ی «پخش‌شده‌ها» ساخته شده است؟ (برای تشخیص اولین بارگذاری) */
export function hasPlayedHistory(userId: number): boolean {
  try {
    return localStorage.getItem(playedIdsStorageKey(userId)) !== null;
  } catch {
    return false; // storage مسدود: هر نشست بی‌صدا شروع می‌شود تا هجوم اعلان قدیمی نداشته باشیم
  }
}
