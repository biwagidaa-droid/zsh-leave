export type Role = "employee" | "manager" | "hr" | "admin" | "exec";

export const ROLE_LABEL: Record<Role, string> = {
  employee: "کارمند",
  manager: "مدیر مستقیم",
  hr: "منابع انسانی",
  admin: "مدیر سامانه",
  exec: "گزارش‌خوان ارشد",
};

export const STATUS_LABEL: Record<string, string> = {
  PENDING: "در انتظار تأیید",
  ESCALATED: "ارجاع‌شده",
  APPROVED: "تأییدشده",
  REJECTED: "ردشده",
  CANCELLED: "لغوشده",
  AUTO_CANCELLED: "لغوشده خودکار",
  WITHDRAWAL_PENDING: "در انتظار لغو",
};

export const STATUS_TONE: Record<string, "warn" | "info" | "ok" | "danger" | "muted" | "accent"> = {
  PENDING: "warn",
  ESCALATED: "accent",
  APPROVED: "ok",
  REJECTED: "danger",
  CANCELLED: "muted",
  AUTO_CANCELLED: "muted",
  WITHDRAWAL_PENDING: "info",
};

export function hasAny(roles: Role[], ...need: Role[]): boolean {
  return need.some((r) => roles.includes(r));
}

export function primaryRole(roles: Role[]): Role {
  const order: Role[] = ["admin", "hr", "manager", "exec", "employee"];
  return order.find((r) => roles.includes(r)) ?? "employee";
}

/** وضعیت‌هایی که هنوز تصمیم نهایی نگرفته‌اند. */
export const OPEN_STATUSES = ["PENDING", "ESCALATED"] as const;

export function isOpenStatus(status: string): boolean {
  return (OPEN_STATUSES as readonly string[]).includes(status);
}

/** ترتیب نمایش وضعیت‌ها در فیلترها. */
export const STATUS_ORDER = ["PENDING", "ESCALATED", "APPROVED", "REJECTED", "CANCELLED", "AUTO_CANCELLED", "WITHDRAWAL_PENDING"] as const;
