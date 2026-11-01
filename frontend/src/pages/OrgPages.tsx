import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { asApiError, errorMessage } from "../api/errors";
import type { Company, ContractPeriod, Department, Employee, Holiday } from "../api/types";
import { JalaliDateField } from "../components/JalaliDateField";
import {
  Badge, Button, Card, Checkbox, ConfirmDialog, DataTable, ErrorState, Field, Input, LoadingBlock,
  PageHeader, SearchInput, Select, type Column,
} from "../components/ui";
import { camelFields } from "../lib/forms";
import { focusFirstInvalid, useDebounced } from "../lib/hooks";
import { MONTH_NAMES, PY_WEEKDAY_LABELS, formatJalaliSafe, monthLength, todayIso, MAX_YEAR, MIN_YEAR } from "../lib/jalali";
import { hasAny } from "../lib/roles";
import { useAsync } from "../lib/useAsync";
import { useAuth } from "../state/Auth";
import { useToast } from "../state/Toast";

export function EmployeesPage() {
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const [q, setQ] = useState("");
  const dq = useDebounced(q.trim(), 300);
  const { data, reload, error, loading } = useAsync(() => api.employees(dq), [dq]);
  const { data: companies } = useAsync(() => api.companies(), []);
  const { user } = useAuth();
  const canEdit = hasAny(user?.roles ?? [], "hr", "admin");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [companyId, setCid] = useState<number | "">("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  // شرکت پیش‌فرض: نخستین شرکت موجود (به‌جای شناسه‌ی ثابت ۱)
  useEffect(() => {
    if (companyId === "" && companies?.length) setCid(companies[0].id);
  }, [companies, companyId]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const found: Record<string, string> = {};
    if (!name.trim()) found.displayName = "نام را وارد کنید";
    if (!code.trim()) found.personnelCode = "کد پرسنلی را وارد کنید";
    if (companyId === "") found.companyId = "شرکت را انتخاب کنید";
    setErrors(found);
    if (Object.keys(found).length || companyId === "") { focusFirstInvalid(formRef.current); return; }
    setBusy(true);
    try {
      await api.saveEmployee({ displayName: name.trim(), personnelCode: code.trim(), companyId: Number(companyId) });
      toast("ثبت شد", "success");
      setName(""); setCode("");
      await reload();
    } catch (err) {
      const ae = asApiError(err);
      toast(ae.message, "danger");
      setErrors(camelFields(ae.fields));
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<Employee>[] = [
    { key: "displayName", label: "نام" },
    { key: "personnelCode", label: "کد", ltr: true },
    { key: "companyName", label: "شرکت" },
    { key: "departmentName", label: "واحد" },
    { key: "managerName", label: "مدیر", render: (e) => e.managerName ?? "—" },
    { key: "isActive", label: "وضعیت", render: (e) => <Badge tone={e.isActive ? "ok" : "muted"}>{e.isActive ? "فعال" : "غیرفعال"}</Badge> },
  ];

  return (
    <>
      <PageHeader title="کارکنان" subtitle="جستجوی جانشین فقط افراد فعال را نشان می‌دهد" />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      <div className="toolbar" role="search">
        <SearchInput aria-label="جستجوی کارمند بر اساس نام یا کد پرسنلی" placeholder="نام یا کد پرسنلی" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {canEdit && (
        <Card title="افزودن (HR/سامانه)">
          <form onSubmit={submit} ref={formRef} noValidate>
            <div className="grid grid-3">
              <Field label="نام" required error={errors.displayName}><Input value={name} onChange={(e) => setName(e.target.value)} /></Field>
              <Field label="کد پرسنلی" required error={errors.personnelCode}>
                <Input value={code} dir="ltr" className="ltr-input" onChange={(e) => setCode(e.target.value)} />
              </Field>
              <Field label="شرکت" required error={errors.companyId}>
                <Select value={companyId} onChange={(e) => setCid(e.target.value ? Number(e.target.value) : "")}>
                  {companies?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
            </div>
            <Button type="submit" loading={busy}>ذخیره</Button>
          </form>
        </Card>
      )}
      <div className="mt">
        {loading && !data ? <LoadingBlock /> : <DataTable columns={columns} rows={data ?? []} rowKey={(e) => e.id} caption="فهرست کارکنان" />}
      </div>
    </>
  );
}

export function OrganizationPage() {
  const { user } = useAuth();
  const canEdit = hasAny(user?.roles ?? [], "admin");
  const toast = useToast();
  const { data: companies, reload: rc, error: ce, loading: cl } = useAsync(() => api.companies(), []);
  const { data: deps, reload: rd, error: de, loading: dl } = useAsync(() => api.departments(), []);
  const [cname, setCn] = useState("");
  const [ccode, setCc] = useState("");
  const [dname, setDn] = useState("");
  const [dcode, setDc] = useState("");
  const [companyId, setCid] = useState<number | "">("");
  const [cErr, setCErr] = useState<Record<string, string>>({});
  const [dErr, setDErr] = useState<Record<string, string>>({});
  const [cBusy, setCBusy] = useState(false);
  const [dBusy, setDBusy] = useState(false);
  const cForm = useRef<HTMLFormElement>(null);
  const dForm = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (companyId === "" && companies?.length) setCid(companies[0].id);
  }, [companies, companyId]);

  const addCompany = async (e: FormEvent) => {
    e.preventDefault();
    if (cBusy) return;
    const found: Record<string, string> = {};
    if (!ccode.trim()) found.code = "کد شرکت را وارد کنید";
    if (!cname.trim()) found.name = "نام شرکت را وارد کنید";
    setCErr(found);
    if (Object.keys(found).length) { focusFirstInvalid(cForm.current); return; }
    setCBusy(true);
    try {
      await api.saveCompany({ code: ccode.trim(), name: cname.trim() });
      toast("شرکت افزوده شد", "success");
      setCc(""); setCn("");
      await rc();
    } catch (err) {
      const ae = asApiError(err);
      toast(ae.message, "danger");
      setCErr(camelFields(ae.fields));
    } finally {
      setCBusy(false);
    }
  };

  const addDepartment = async (e: FormEvent) => {
    e.preventDefault();
    if (dBusy) return;
    const found: Record<string, string> = {};
    if (companyId === "") found.companyId = "شرکت را انتخاب کنید";
    if (!dcode.trim()) found.code = "کد واحد را وارد کنید";
    if (!dname.trim()) found.name = "نام واحد را وارد کنید";
    setDErr(found);
    if (Object.keys(found).length || companyId === "") { focusFirstInvalid(dForm.current); return; }
    setDBusy(true);
    try {
      await api.saveDepartment({ code: dcode.trim(), name: dname.trim(), companyId: Number(companyId) });
      toast("واحد افزوده شد", "success");
      setDc(""); setDn("");
      await rd();
    } catch (err) {
      const ae = asApiError(err);
      toast(ae.message, "danger");
      setDErr(camelFields(ae.fields));
    } finally {
      setDBusy(false);
    }
  };

  const companyName = (id: number) => companies?.find((c) => c.id === id)?.name ?? "—";
  const companyCols: Column<Company>[] = [
    { key: "code", label: "کد", ltr: true },
    { key: "name", label: "نام" },
    { key: "isActive", label: "وضعیت", render: (c) => <Badge tone={c.isActive ? "ok" : "muted"}>{c.isActive ? "فعال" : "غیرفعال"}</Badge> },
  ];
  const depCols: Column<Department>[] = [
    { key: "code", label: "کد", ltr: true },
    { key: "name", label: "نام" },
    { key: "companyId", label: "شرکت", render: (d) => companyName(d.companyId) },
  ];

  return (
    <>
      <PageHeader title="ساختار سازمانی" subtitle="حذف شرکت/واحد دارای وابسته در Backend ممنوع است" />
      {(ce || de) && <ErrorState message={ce ?? de ?? ""} onRetry={() => { void rc(); void rd(); }} />}
      <div className="grid grid-2">
        <Card title="شرکت‌ها">
          {canEdit && (
            <form onSubmit={addCompany} ref={cForm} noValidate>
              <Field label="کد" required error={cErr.code}><Input value={ccode} dir="ltr" className="ltr-input" onChange={(e) => setCc(e.target.value)} /></Field>
              <Field label="نام" required error={cErr.name}><Input value={cname} onChange={(e) => setCn(e.target.value)} /></Field>
              <Button type="submit" loading={cBusy}>افزودن شرکت</Button>
            </form>
          )}
          <div className={canEdit ? "mt" : undefined}>
            {cl && !companies ? <LoadingBlock /> : <DataTable columns={companyCols} rows={companies ?? []} rowKey={(c) => c.id} caption="شرکت‌ها" />}
          </div>
        </Card>
        <Card title="واحدها">
          {canEdit && (
            <form onSubmit={addDepartment} ref={dForm} noValidate>
              <Field label="شرکت" required error={dErr.companyId}>
                <Select value={companyId} onChange={(e) => setCid(e.target.value ? Number(e.target.value) : "")}>
                  {companies?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </Select>
              </Field>
              <Field label="کد" required error={dErr.code}><Input value={dcode} dir="ltr" className="ltr-input" onChange={(e) => setDc(e.target.value)} /></Field>
              <Field label="نام" required error={dErr.name}><Input value={dname} onChange={(e) => setDn(e.target.value)} /></Field>
              <Button type="submit" loading={dBusy}>افزودن واحد</Button>
            </form>
          )}
          <div className={canEdit ? "mt" : undefined}>
            {dl && !deps ? <LoadingBlock /> : <DataTable columns={depCols} rows={deps ?? []} rowKey={(d) => d.id} caption="واحدها" />}
          </div>
        </Card>
      </div>
    </>
  );
}

export function HolidaysPage() {
  const { user } = useAuth();
  const canManage = hasAny(user?.roles ?? [], "hr", "admin");
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const { data, reload, error, loading } = useAsync(() => api.holidays(), []);
  const [label, setLabel] = useState("");
  const [m, setM] = useState(1);
  const [d, setD] = useState("1");
  const [annual, setAnnual] = useState(true);
  const [year, setYear] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [toDelete, setToDelete] = useState<Holiday | null>(null);
  const [deleting, setDeleting] = useState(false);

  const sorted = [...(data ?? [])].sort((a, b) => a.jalaliMonth - b.jalaliMonth || a.jalaliDay - b.jalaliDay || (a.jalaliYear ?? 0) - (b.jalaliYear ?? 0));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const found: Record<string, string> = {};
    const day = Number(d);
    const yr = Number(year);
    if (!label.trim()) found.label = "عنوان را وارد کنید";
    if (!Number.isInteger(day) || day < 1) found.jalaliDay = "روز نامعتبر است";
    if (!annual) {
      if (!Number.isInteger(yr) || yr < MIN_YEAR || yr > MAX_YEAR) found.jalaliYear = `سال باید بین ${MIN_YEAR} و ${MAX_YEAR} باشد`;
    }
    if (!found.jalaliDay) {
      // برای تعطیلی سالانه، بلندترین طول ممکن ماه (سال کبیسه) پذیرفته می‌شود
      const limit = annual ? (m <= 6 ? 31 : 30) : (!found.jalaliYear ? monthLength(yr, m) : 31);
      if (day > limit) found.jalaliDay = `${MONTH_NAMES[m - 1]} حداکثر ${limit} روز دارد`;
    }
    setErrors(found);
    if (Object.keys(found).length) { focusFirstInvalid(formRef.current); return; }
    setBusy(true);
    try {
      await api.saveHoliday({ scope: "*", jalaliYear: annual ? null : yr, jalaliMonth: m, jalaliDay: day, label: label.trim() });
      toast("ثبت شد", "success");
      setLabel("");
      await reload();
    } catch (err) {
      const ae = asApiError(err);
      toast(ae.message, "danger");
      setErrors(camelFields(ae.fields));
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.deleteHoliday(toDelete.id);
      toast("حذف شد", "success");
      setToDelete(null);
      await reload();
    } catch (err) {
      toast(errorMessage(err), "danger");
    } finally {
      setDeleting(false);
    }
  };

  const columns: Column<Holiday>[] = [
    { key: "label", label: "عنوان" },
    { key: "date", label: "تاریخ شمسی", render: (h) => `${h.jalaliDay} ${MONTH_NAMES[h.jalaliMonth - 1] ?? h.jalaliMonth}${h.jalaliYear ? ` ${h.jalaliYear}` : " (هر سال)"}` },
    { key: "scope", label: "محدوده", render: (h) => (h.scope === "*" ? "ملی" : h.scope) },
    {
      key: "actions", label: "عملیات",
      render: (h) => (canManage
        ? <Button variant="danger" size="sm" onClick={() => setToDelete(h)}>حذف</Button>
        : "—"),
    },
  ];

  return (
    <>
      <PageHeader title="تعطیلات رسمی" subtitle="منبع: ثبت دستی شمسی. مبنای تغییر مقدار تأییدشده مرخصی نیستند." />
      {error && <ErrorState message={error} onRetry={() => void reload()} />}
      {canManage && (
        <Card title="ثبت تعطیلی">
          <form onSubmit={submit} ref={formRef} noValidate>
            <div className="grid grid-3">
              <Field label="عنوان" required error={errors.label}><Input value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
              <Field label="ماه" required>
                <Select value={m} onChange={(e) => setM(Number(e.target.value))}>
                  {MONTH_NAMES.map((n, i) => <option key={n} value={i + 1}>{n}</option>)}
                </Select>
              </Field>
              <Field label="روز" required error={errors.jalaliDay}>
                <Input type="number" min={1} max={31} value={d} dir="ltr" className="ltr-input" onChange={(e) => setD(e.target.value)} />
              </Field>
            </div>
            <Checkbox label="سالانه (بدون سال مشخص)" checked={annual} onChange={(e) => setAnnual(e.target.checked)} />
            {!annual && (
              <Field label="سال شمسی" required error={errors.jalaliYear}>
                <Input type="number" min={MIN_YEAR} max={MAX_YEAR} value={year} dir="ltr" className="ltr-input" placeholder={String(new Date().getFullYear() - 621)} onChange={(e) => setYear(e.target.value)} />
              </Field>
            )}
            <Button type="submit" loading={busy}>ذخیره</Button>
          </form>
        </Card>
      )}
      <div className="mt">
        {loading && !data ? <LoadingBlock /> : <DataTable columns={columns} rows={sorted} rowKey={(h) => h.id} caption="تعطیلات رسمی" />}
      </div>
      {toDelete && (
        <ConfirmDialog
          title="حذف تعطیلی"
          message={<>تعطیلی «{toDelete.label}» حذف شود؟</>}
          confirmLabel="حذف"
          danger
          busy={deleting}
          onConfirm={() => void confirmDelete()}
          onCancel={() => setToDelete(null)}
        />
      )}
    </>
  );
}

const DEFAULT_WORK_DAYS = [5, 6, 0, 1, 2]; // شنبه تا چهارشنبه (شاخص پایتون)
const WEEK_ORDER = [5, 6, 0, 1, 2, 3, 4]; // ترتیب نمایش ایرانی

export function ContractsPage() {
  const toast = useToast();
  const formRef = useRef<HTMLFormElement>(null);
  const { data: employees, error: empError } = useAsync(() => api.employees(), []);
  const [employeeId, setEmp] = useState<number | "">("");
  const { data, reload, error, loading } = useAsync(
    () => (employeeId === "" ? Promise.resolve([]) : api.contracts(Number(employeeId))), [employeeId],
  );
  const [start, setStart] = useState(todayIso());
  const [end, setEnd] = useState("");
  const [percent, setPercent] = useState("100");
  const [workDays, setWorkDays] = useState<number[]>(DEFAULT_WORK_DAYS);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (employeeId === "" && employees?.length) setEmp(employees[0].id);
  }, [employees, employeeId]);

  const toggleDay = (day: number, on: boolean) =>
    setWorkDays((xs) => (on ? [...xs, day] : xs.filter((x) => x !== day)));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const found: Record<string, string> = {};
    const pct = Number(percent);
    if (employeeId === "") found.employeeId = "کارمند را انتخاب کنید";
    if (!start) found.start = "تاریخ شروع را وارد کنید";
    if (end && start && end < start) found.end = "پایان نباید قبل از شروع باشد";
    if (!workDays.length) found.workDays = "دست‌کم یک روز کاری انتخاب کنید";
    if (!Number.isFinite(pct) || pct <= 0 || pct > 100) found.contractPercent = "درصد باید بین ۱ تا ۱۰۰ باشد";
    setErrors(found);
    if (Object.keys(found).length || employeeId === "") { focusFirstInvalid(formRef.current); return; }
    setBusy(true);
    try {
      await api.saveContract({ employeeId: Number(employeeId), start, end: end || null, workDays: [...workDays], contractPercent: pct });
      toast("ثبت شد", "success");
      await reload();
    } catch (err) {
      const ae = asApiError(err);
      toast(ae.message, "danger");
      setErrors(camelFields(ae.fields));
    } finally {
      setBusy(false);
    }
  };

  const columns: Column<ContractPeriod>[] = [
    { key: "start", label: "شروع", render: (c) => formatJalaliSafe(c.start) },
    { key: "end", label: "پایان", render: (c) => (c.end ? formatJalaliSafe(c.end) : "نامحدود") },
    { key: "workDays", label: "روزهای کاری", render: (c) => WEEK_ORDER.filter((x) => c.workDays.includes(x)).map((x) => PY_WEEKDAY_LABELS[x]).join("، ") },
    { key: "contractPercent", label: "درصد قرارداد", render: (c) => `${c.contractPercent}٪` },
  ];

  return (
    <>
      <PageHeader title="دوره‌های الگوی کاری" subtitle="بازه هم‌پوشان مجاز نیست" />
      {(error || empError) && <ErrorState message={error ?? empError ?? ""} onRetry={() => void reload()} />}
      <Field label="کارمند">
        <Select value={employeeId} onChange={(e) => setEmp(e.target.value ? Number(e.target.value) : "")}>
          {employees?.map((e) => <option key={e.id} value={e.id}>{e.displayName}</option>)}
        </Select>
      </Field>
      <Card title="دوره جدید">
        <form onSubmit={submit} ref={formRef} noValidate>
          <div className="grid grid-3">
            <Field label="شروع" required error={errors.start}><JalaliDateField value={start} onChange={setStart} /></Field>
            <Field label="پایان (اختیاری)" error={errors.end} hint="خالی = نامحدود">
              <JalaliDateField value={end} min={start || undefined} onChange={setEnd} />
            </Field>
            <Field label="درصد قرارداد" required error={errors.contractPercent}>
              <Input type="number" min={1} max={100} value={percent} dir="ltr" className="ltr-input" onChange={(e) => setPercent(e.target.value)} />
            </Field>
          </div>
          <fieldset className="field-group" aria-describedby={errors.workDays ? "wd-err" : undefined}>
            <legend>روزهای کاری (پیش‌فرض شنبه تا چهارشنبه)</legend>
            <div className="check-row">
              {WEEK_ORDER.map((day) => (
                <Checkbox key={day} label={PY_WEEKDAY_LABELS[day]} checked={workDays.includes(day)} onChange={(e) => toggleDay(day, e.target.checked)} />
              ))}
            </div>
            {errors.workDays && <div className="error" id="wd-err" role="alert">{errors.workDays}</div>}
          </fieldset>
          <Button type="submit" loading={busy} disabled={employeeId === ""}>افزودن دوره</Button>
        </form>
      </Card>
      <div className="mt">
        {loading && !data ? <LoadingBlock /> : <DataTable columns={columns} rows={data ?? []} rowKey={(c) => c.id} caption="دوره‌های الگوی کاری" />}
      </div>
    </>
  );
}
