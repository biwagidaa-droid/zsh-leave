import { DEFAULT_CLIENT_POLICY } from "../lib/clientPolicy";
import { ApiError, UNAUTHORIZED_EVENT } from "./errors";
import type { Api, LeaveDraft, RequestFilters } from "./contract";
import type { ApiErrorBody } from "./types";

function csrf(): string {
  const m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

/** پیام فارسی پیش‌فرض بر اساس کد وضعیت، وقتی بدنه خطا از سرور قابل‌خواندن نباشد. */
function fallbackMessage(status: number): string {
  switch (status) {
    case 400: return "درخواست نامعتبر است";
    case 401: return "نشست شما معتبر نیست؛ دوباره وارد شوید";
    case 403: return "دسترسی لازم را ندارید";
    case 404: return "مورد درخواستی یافت نشد";
    case 409: return "درخواست با وضعیت فعلی تعارض دارد";
    case 422: return "اطلاعات واردشده معتبر نیست";
    case 429: return "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید";
    default: return status >= 500 ? "خطای سرور؛ کمی بعد دوباره تلاش کنید" : "خطای ناشناخته";
  }
}

function isErrorBody(v: unknown): v is Partial<ApiErrorBody> {
  return typeof v === "object" && v !== null;
}

/** مسیرهایی که 401 آن‌ها «نشست منقضی‌شده» نیست و نباید رویداد خروج اجباری بفرستند. */
const AUTH_PATHS = new Set(["/auth/login", "/auth/me"]);

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  headers.set("Accept", "application/json");
  const token = csrf();
  if (token) headers.set("X-CSRFToken", token);

  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { credentials: "include", ...init, headers });
  } catch {
    throw new ApiError(0, { code: "network", message_fa: "ارتباط با سرور برقرار نشد؛ اتصال شبکه را بررسی کنید" });
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  let parsed = true;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      parsed = false;
    }
  }

  if (!res.ok) {
    if (res.status === 401 && !AUTH_PATHS.has(path.split("?")[0])) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    const body: Partial<ApiErrorBody> = parsed && isErrorBody(data) ? data : {};
    throw new ApiError(res.status, {
      code: body.code ?? "http",
      message_fa: body.message_fa ?? fallbackMessage(res.status),
      fields: body.fields,
    });
  }

  if (!parsed) throw new ApiError(res.status, { code: "bad_response", message_fa: "پاسخ نامعتبر از سرور دریافت شد" });
  return data as T;
}

export const httpApi: Api = {
  login: (username, password) => req("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  logout: () => req("/auth/logout", { method: "POST" }),
  me: () => req("/auth/me"),
  changePassword: (current, next) => req("/auth/password", { method: "POST", body: JSON.stringify({ current, next }) }),
  listTypes: () => req("/leave-types/"),
  saveType: (t) => req(t.id ? `/leave-types/${t.id}/` : "/leave-types/", { method: t.id ? "PATCH" : "POST", body: JSON.stringify(t) }),
  listRequests: (f: RequestFilters) => {
    const q = new URLSearchParams();
    if (f.page) q.set("page", String(f.page));
    if (f.status) q.set("status", f.status);
    if (f.q) q.set("q", f.q);
    if (f.mine) q.set("scope", "me");
    if (f.team) q.set("scope", "team");
    const qs = q.toString();
    return req(`/leave-requests/${qs ? `?${qs}` : ""}`);
  },
  getRequest: (id) => req(`/leave-requests/${id}/`),
  createRequest: (d) => req("/leave-requests/", { method: "POST", body: JSON.stringify(d) }),
  updateRequest: (id, d) => req(`/leave-requests/${id}/`, { method: "PATCH", body: JSON.stringify(d) }),
  actRequest: (id, action, reason) => req(`/leave-requests/${id}/${action}`, { method: "POST", body: JSON.stringify({ reason }) }),
  listComments: (id) => req(`/leave-requests/${id}/comments/`),
  addComment: (id, body) => req(`/leave-requests/${id}/comments/`, { method: "POST", body: JSON.stringify({ body }) }),
  listAttachments: (id) => req(`/leave-requests/${id}/attachments/`),
  addAttachment: (id, fileName) => req(`/leave-requests/${id}/attachments/`, { method: "POST", body: JSON.stringify({ fileName }) }),
  balances: (year, employeeId) => req(`/balances/?year=${year}${employeeId ? `&employee=${employeeId}` : ""}`),
  entitlements: (year) => req(`/entitlements/?year=${year}`),
  adjustEntitlement: (id, days, reason) => req(`/entitlements/${id}/adjust`, { method: "POST", body: JSON.stringify({ days, reason }) }),
  importEntitlements: (csv, dryRun) => req(`/entitlements/import/?dry_run=${dryRun ? "1" : "0"}`, { method: "POST", body: JSON.stringify({ csv }) }),
  recordAbsence: (d: LeaveDraft) => req("/hr/absences/", { method: "POST", body: JSON.stringify(d) }),
  calendar: (from, to, scope) => req(`/calendar/events/?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}&scope=${scope}`),
  calendarHolidays: (from, to) => req(`/calendar/holidays/?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  holidays: () => req("/holidays/"),
  saveHoliday: (h) => req(h.id ? `/holidays/${h.id}/` : "/holidays/", { method: h.id ? "PATCH" : "POST", body: JSON.stringify(h) }),
  deleteHoliday: (id, reason) => req(`/holidays/${id}/`, { method: "DELETE", body: JSON.stringify({ reason }) }),
  notifications: () => req("/notifications/"),
  readNotification: (id) => req(`/notifications/${id}/read`, { method: "POST" }),
  employees: (q) => req(`/employees/${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  saveEmployee: (e) => req(e.id ? `/employees/${e.id}/` : "/employees/", { method: e.id ? "PATCH" : "POST", body: JSON.stringify(e) }),
  companies: () => req("/companies/"),
  departments: () => req("/departments/"),
  saveCompany: (c) => req(c.id ? `/companies/${c.id}/` : "/companies/", { method: c.id ? "PATCH" : "POST", body: JSON.stringify(c) }),
  saveDepartment: (d) => req(d.id ? `/departments/${d.id}/` : "/departments/", { method: d.id ? "PATCH" : "POST", body: JSON.stringify(d) }),
  contracts: (employeeId) => req(`/employees/${employeeId}/contract-periods/`),
  saveContract: (p) => req(`/employees/${p.employeeId}/contract-periods/`, { method: "POST", body: JSON.stringify(p) }),
  coverage: (from, to) => req(`/coverage/?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`),
  reports: (kind) => req(`/reports/${encodeURIComponent(kind)}`),
  settings: () => req("/admin/settings/"),
  saveSetting: (key, value, reason) => req("/admin/settings/", { method: "POST", body: JSON.stringify({ key, value, reason }) }),
  jobs: () => req("/admin/jobs/"),
  audit: () => req("/audit/events/"),
  health: () => req("/health/ready"),
  estimate: (employeeId, start, end) => req(`/working-days/estimate?employee=${employeeId ?? ""}&start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`),
  async clientPolicy() {
    try {
      return await req("/policy/client");
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) return DEFAULT_CLIENT_POLICY;
      throw e;
    }
  },
  async bradfordNotes() {
    try {
      return await req("/hr/bradford-notes/");
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 501)) return [];
      throw e;
    }
  },
  saveBradfordNote: (employeeId, body) => req("/hr/bradford-notes/", { method: "POST", body: JSON.stringify({ employeeId, body }) }),
};
