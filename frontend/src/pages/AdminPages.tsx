import { FormEvent, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { asApiError, errorMessage } from "../api/errors";
import type { AuditRow, JobRow, SettingItem } from "../api/types";
import {
  Badge, Button, Card, DataTable, DetailList, Empty, ErrorState, Field, Input, LoadingBlock,
  PageHeader, SearchInput, Select, type Column,
} from "../components/ui";
import { formatJalaliDateTime } from "../lib/jalali";
import { ROLE_LABEL } from "../lib/roles";
import { useAsync } from "../lib/useAsync";
import { useAuth } from "../state/Auth";
import { useToast } from "../state/Toast";

const GROUP_LABEL: Record<string, string> = {
  policy: "سیاست مرخصی",
  privacy: "حریم خصوصی",
  workflow: "گردش کار",
  holidays: "تعطیلات",
  bradford: "تحلیل Bradford",
};

/** تبدیل متن ورودی به نوع مقدار تنظیم؛ هم‌خوان با رفتار قبلی (رشته‌ی عددی ← عدد، true/false ← بولین، خالی ← null). */
function parseSettingValue(raw: string, s: SettingItem): unknown {
  if (raw === "") return null;
  if (raw === "true" || raw === "false") return raw === "true";
  const numeric = raw.trim() !== "" && !Number.isNaN(Number(raw));
  if (numeric && (typeof s.value === "number" || typeof s.default === "number" || s.default === null || /^\d/.test(String(s.default)))) {
    return Number(raw);
  }
  return raw;
}

function display(v: unknown): string {
  return v === null || v === undefined ? "" : String(v);
}

export function SettingsPage() {
  const toast = useToast();
  const { data, reload, error, loading } = useAsync(() => api.settings(), []);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const groups = Array.from(new Set(data?.map((s) => s.group) ?? []));

  const save = async (s: SettingItem, raw: string) => {
    if (!reason.trim()) {
      setReasonError("برای ذخیره‌ی تغییر، دلیل را وارد کنید");
      document.querySelector<HTMLInputElement>("#setting-reason-box input")?.focus();
      return;
    }
    setReasonError("");
    setSaving(s.key);
    try {
      await api.saveSetting(s.key, parseSettingValue(raw, s), reason.trim());
      setDraft((d) => {
        const { [s.key]: _removed, ...rest } = d;
        return rest;
      });
      await reload();
      toast("ذخیره شد", "success");
    } catch (e) {
      toast(errorMessage(e), "danger");
    } finally {
      setSaving(null);
    }
  };

  return (
    <>
      <PageHeader title="تنظیمات سامانه" subtitle="تغییر نیازمند دلیل است و در حسابرسی ثبت می‌شود. مقدارهای خالی یعنی پیکربندی‌نشده." />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      <div className="card mb" id="setting-reason-box">
        <Field label="دلیل تغییر (الزامی برای ذخیره)" required error={reasonError}>
          <Input value={reason} onChange={(e) => { setReason(e.target.value); setReasonError(""); }} />
        </Field>
      </div>
      {loading && !data ? <LoadingBlock /> : null}
      {groups.map((g) => (
        <Card key={g} title={GROUP_LABEL[g] ?? g}>
          {data?.filter((s) => s.group === g).map((s) => {
            const current = display(s.value);
            const value = draft[s.key] ?? current;
            const dirty = s.key in draft && draft[s.key] !== current;
            const isDefault = display(s.default) === current;
            const submit = (e: FormEvent) => { e.preventDefault(); if (dirty) void save(s, value); };
            return (
              <form key={s.key} className="setting-row" onSubmit={submit} noValidate>
                <Field label={s.labelFa} hint={s.key}>
                  <div className="toolbar">
                    {typeof s.default === "boolean" ? (
                      <Select value={value} onChange={(e) => setDraft((d) => ({ ...d, [s.key]: e.target.value }))}>
                        <option value="true">فعال</option>
                        <option value="false">غیرفعال</option>
                      </Select>
                    ) : (
                      <Input value={value} dir="ltr" className="ltr-input" onChange={(e) => setDraft((d) => ({ ...d, [s.key]: e.target.value }))} />
                    )}
                    <Button type="submit" size="sm" loading={saving === s.key} disabled={!dirty || saving !== null}>ذخیره</Button>
                    {dirty && (
                      <Button variant="ghost" size="sm" onClick={() => setDraft((d) => { const { [s.key]: _r, ...rest } = d; return rest; })}>لغو</Button>
                    )}
                    {!dirty && !isDefault && (
                      <Button variant="ghost" size="sm" disabled={saving !== null} onClick={() => void save(s, display(s.default))}>
                        بازگشت به پیش‌فرض
                      </Button>
                    )}
                  </div>
                </Field>
              </form>
            );
          })}
        </Card>
      ))}
    </>
  );
}

const STATUS_TONE: Record<string, "ok" | "danger" | "warn" | "muted"> = { ok: "ok", success: "ok", failed: "danger", error: "danger", skipped: "warn" };

export function JobsPage() {
  const { data: jobs, error, loading, reload } = useAsync(() => api.jobs(), []);
  const { data: health } = useAsync(() => api.health().catch(() => null), []);
  const columns: Column<JobRow>[] = [
    { key: "job", label: "Job" },
    { key: "started", label: "شروع", render: (j) => formatJalaliDateTime(j.started) },
    { key: "finished", label: "پایان", render: (j) => formatJalaliDateTime(j.finished) },
    { key: "status", label: "وضعیت", render: (j) => <Badge tone={STATUS_TONE[j.status] ?? "muted"}>{j.status}</Badge> },
    { key: "error", label: "توضیح", render: (j) => j.error || "—" },
  ];
  return (
    <>
      <PageHeader title="Jobها و سلامت" subtitle="یادآوری و ارجاع تا تعیین مهلت (OQ-04) غیرفعال می‌مانند" />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      <div className="grid grid-3 mb">
        <Card title="Live"><Badge tone={health?.live ? "ok" : "danger"}>{health?.live ? "فعال" : "خیر"}</Badge></Card>
        <Card title="Ready"><Badge tone={health?.ready ? "ok" : "danger"}>{health?.ready ? "آماده" : "خیر"}</Badge></Card>
        <Card title="آخرین Job">{health?.lastJob ?? "—"}</Card>
      </div>
      {loading && !jobs ? <LoadingBlock /> : <DataTable columns={columns} rows={jobs ?? []} rowKey={(j) => j.id} caption="اجرای Jobها" />}
    </>
  );
}

export function AuditPage() {
  const { data, error, loading, reload } = useAsync(() => api.audit(), []);
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return data ?? [];
    return (data ?? []).filter((a) => [a.actorName ?? "سامانه", a.action, a.entity, a.entityId, a.reason, a.result].some((x) => x.toLowerCase().includes(t)));
  }, [data, q]);
  const columns: Column<AuditRow>[] = [
    { key: "createdAt", label: "زمان", render: (a) => formatJalaliDateTime(a.createdAt) },
    { key: "actorName", label: "عامل", render: (a) => a.actorName ?? "سامانه" },
    { key: "action", label: "عمل", render: (a) => <code>{a.action}</code> },
    { key: "entity", label: "موجودیت", render: (a) => `${a.entity} #${a.entityId}` },
    { key: "result", label: "نتیجه", render: (a) => <Badge tone={a.result === "ok" ? "ok" : "danger"}>{a.result}</Badge> },
    { key: "reason", label: "دلیل", render: (a) => a.reason || "—" },
  ];
  return (
    <>
      <PageHeader title="حسابرسی" subtitle="فقط خواندنی و append-only" />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      <div className="toolbar" role="search">
        <SearchInput aria-label="جستجو در رویدادهای حسابرسی" placeholder="جستجو در عامل، عمل یا موجودیت" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <LoadingBlock /> : (
        <DataTable columns={columns} rows={rows} rowKey={(a) => a.id} caption="رویدادهای حسابرسی" empty={<Empty title="رویدادی یافت نشد" />} />
      )}
    </>
  );
}

// مرکز اعلان به NotificationCenter.tsx منتقل شد (همه‌ی قابلیت‌های قبلی: فهرست، «خواندم»، «همه را خواندم» و لینک درخواست حفظ شده است).
export { NotificationsPage } from "./NotificationCenter";

const MIN_PASSWORD = 10;

export function ProfilePage() {
  const { user } = useAuth();
  const toast = useToast();
  const [current, setCur] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  if (!user) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const found: Record<string, string> = {};
    if (!current) found.current = "رمز فعلی را وارد کنید";
    if (next.length < MIN_PASSWORD) found.next = `رمز جدید باید حداقل ${MIN_PASSWORD} نویسه باشد`;
    else if (next === current) found.next = "رمز جدید باید با رمز فعلی متفاوت باشد";
    if (confirm !== next) found.confirm = "تکرار رمز با رمز جدید یکسان نیست";
    setErrors(found);
    if (Object.keys(found).length) return;
    setBusy(true);
    try {
      await api.changePassword(current, next);
      toast("رمز به‌روز شد", "success");
      setCur(""); setNext(""); setConfirm("");
    } catch (err) {
      const ae = asApiError(err);
      toast(ae.message, "danger");
      if (ae.fields.current) setErrors({ current: ae.fields.current });
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader title="پروفایل" />
      <div className="grid grid-2">
        <Card title="مشخصات">
          <DetailList
            items={[
              { label: "نام", value: user.displayName },
              { label: "نام کاربری", value: <span className="ltr">{user.username}</span> },
              { label: "کد پرسنلی", value: <span className="ltr">{user.personnelCode}</span> },
              { label: "واحد", value: `${user.departmentName} · ${user.companyName}` },
              { label: "مدیر مستقیم", value: user.managerName ?? "—" },
              { label: "ایمیل", value: <span className="ltr">{user.email}</span> },
              { label: "نقش‌ها", value: user.roles.map((r) => ROLE_LABEL[r]).join("، ") },
            ]}
          />
        </Card>
        <Card title="تغییر رمز">
          <form onSubmit={submit} noValidate>
            <Field label="رمز فعلی" required error={errors.current}>
              <Input type="password" value={current} autoComplete="current-password" dir="ltr" className="ltr-input" onChange={(e) => setCur(e.target.value)} />
            </Field>
            <Field label="رمز جدید" required hint={`حداقل ${MIN_PASSWORD} نویسه`} error={errors.next}>
              <Input type="password" value={next} autoComplete="new-password" dir="ltr" className="ltr-input" onChange={(e) => setNext(e.target.value)} />
            </Field>
            <Field label="تکرار رمز جدید" required error={errors.confirm}>
              <Input type="password" value={confirm} autoComplete="new-password" dir="ltr" className="ltr-input" onChange={(e) => setConfirm(e.target.value)} />
            </Field>
            <Button type="submit" loading={busy}>ذخیره</Button>
          </form>
        </Card>
      </div>
    </>
  );
}

export function NotFoundPage() {
  return (
    <>
      <PageHeader title="صفحه پیدا نشد" />
      <Card>
        <p>نشانی واردشده در سامانه وجود ندارد.</p>
        <Link className="btn sm" to="/">بازگشت به داشبورد</Link>
      </Card>
    </>
  );
}
