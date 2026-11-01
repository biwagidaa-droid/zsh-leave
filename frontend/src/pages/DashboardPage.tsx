import { Link } from "react-router-dom";
import { api } from "../api";
import { DonutChart } from "../components/charts";
import { Card, ErrorState, LoadingBlock, PageHeader, Stat, StatusBadge } from "../components/ui";
import { DEFAULT_CLIENT_POLICY } from "../lib/clientPolicy";
import { DeadlineLabel } from "../components/Deadline";
import { deadlineInfo } from "../lib/deadline";
import { fromGregorian, isoToG, jalaliNow, todayIso } from "../lib/jalali";
import { formatRequestRange } from "../lib/leaveDisplay";
import { AUTO_CANCELLED } from "../lib/autoCancel";
import { STATUS_LABEL, STATUS_ORDER, hasAny, isOpenStatus, primaryRole } from "../lib/roles";
import { useAsync } from "../lib/useAsync";
import { useAuth } from "../state/Auth";

function jalaliYearOf(iso: string): number | null {
  try {
    return fromGregorian(isoToG(iso)).jy;
  } catch {
    return null;
  }
}

export function DashboardPage() {
  const { user } = useAuth();
  const year = jalaliNow().jy;
  const roles = user?.roles ?? [];
  const isRequester = hasAny(roles, "employee", "manager", "hr");
  const isApprover = hasAny(roles, "manager", "hr");
  const isAdmin = hasAny(roles, "admin");

  // فقط داده‌ای که برای نقش کاربر معنا دارد درخواست می‌شود (مثلاً مدیر سامانه به رکورد مرخصی دسترسی ندارد)
  const { data: requests, error: reqError, loading: reqLoading, reload: reloadReq } = useAsync(
    () => (isRequester ? api.listRequests({}) : Promise.resolve(null)), [isRequester],
  );
  const { data: balances, loading: balLoading } = useAsync(
    () => (isRequester ? api.balances(year).catch(() => []) : Promise.resolve([])), [year, isRequester],
  );
  const isHr = hasAny(roles, "hr");
  const { data: policy } = useAsync(
    () => (isHr ? api.clientPolicy().catch(() => DEFAULT_CLIENT_POLICY) : Promise.resolve(null)), [isHr],
  );
  const { data: notes, loading: noteLoading } = useAsync(() => api.notifications().catch(() => []), []);
  const { data: health, loading: healthLoading } = useAsync(
    () => (isAdmin ? api.health().catch(() => null) : Promise.resolve(null)), [isAdmin],
  );
  if (!user) return null;

  const role = primaryRole(user.roles);
  const all = requests?.results ?? [];
  const mine = all.filter((r) => r.employeeId === user.employeeId);
  // صف تأیید: فقط درخواست‌های باز که کاربر اجازه‌ی تصمیم‌گیری دارد (canDecide=false صریحاً حذف می‌شود)
  const pendingTeam = all.filter((r) => isOpenStatus(r.status) && r.canDecide !== false);
  const unread = notes?.filter((n) => !n.read).length ?? 0;
  const nearExpiry = all.filter((r) => { const d = deadlineInfo(r, todayIso()); return d?.kind === "waiting" && d.tone === "warn"; }).length;
  const statusData = STATUS_ORDER.map((st) => ({ label: STATUS_LABEL[st], value: all.filter((r) => r.status === st).length }));
  const annual = balances?.find((b) => b.leaveTypeKey === "annual");
  const approvedThisYear = mine.filter((r) => r.status === "APPROVED" && jalaliYearOf(r.start) === year).length;

  return (
    <>
      <PageHeader
        title={`سلام ${user.displayName}`}
        subtitle={role === "admin" ? "نمای سامانه — بدون دسترسی به رکورد فردی مرخصی" : `${user.departmentName} · ${user.companyName}`}
        actions={isRequester ? <Link to="/requests/new" className="btn sm">ثبت درخواست</Link> : undefined}
      />
      {reqError && <ErrorState message={reqError} onRetry={() => void reloadReq()} />}
      {role === "admin" && (
        <div className="grid grid-3 mb">
          <Stat label="سلامت" value={health?.ready ? "آماده" : "نامشخص"} hint={health?.db} loading={healthLoading} />
          <Stat label="آخرین Job" value={health?.lastJob ?? "—"} loading={healthLoading} />
          <Stat label="اعلان‌های نخوانده" value={String(unread)} loading={noteLoading} />
        </div>
      )}
      {role === "exec" && (
        <Card title="نمای هلدینگ">
          <p>گزارش‌های تجمیعی بدون داده فردی. حداقل اندازه گروه در تنظیمات حریم خصوصی اعمال می‌شود.</p>
          <Link to="/reports" className="btn sm">گزارش‌ها</Link>
        </Card>
      )}
      {isRequester && (
        <div className="grid grid-4 mb">
          <Stat label="مانده استحقاقی" value={annual?.remaining ?? "—"} hint={`قابل استفاده ${annual?.usable ?? "—"}`} loading={balLoading} />
          <Stat label="در انتظار" value={String(mine.filter((r) => isOpenStatus(r.status)).length)} loading={reqLoading} />
          <Stat label="تأییدشده امسال" value={String(approvedThisYear)} loading={reqLoading} />
          <Stat label="اعلان نخوانده" value={String(unread)} loading={noteLoading} />
        </div>
      )}
      {isHr && (
        <div className="mb">
          <Card title="نمای منابع انسانی">
            {reqLoading && !requests ? <LoadingBlock /> : (
              <>
                <div className="grid grid-4 mb">
                  <Stat label="لغو خودکار (مهلت تأیید)" value={policy?.autoCancelEnabled ? `${policy.autoCancelDays} روز` : "غیرفعال"} hint="سیاست فعلی" />
                  <Stat label="لغوشده خودکار" value={String(all.filter((r) => r.status === AUTO_CANCELLED).length)} hint="در درخواست‌های بارگذاری‌شده" />
                  <Stat label="نزدیک به انقضا" value={String(nearExpiry)} hint="حداکثر یک روز تا پایان مهلت" />
                  <Stat label="مرخصی ساعتی" value={String(all.filter((r) => r.durationKind === "hourly").length)} hint="در درخواست‌های بارگذاری‌شده" />
                </div>
                <DonutChart
                  title="وضعیت درخواست‌ها"
                  data={statusData}
                  emptyTitle="درخواستی برای نمایش نیست"
                />
                {requests && requests.count > all.length && <p className="hint">آمار بر اساس {all.length} درخواست از {requests.count} درخواست است (صفحه نخست).</p>}
              </>
            )}
          </Card>
        </div>
      )}
      {isApprover && (
        <Card title="صف تأیید" actions={<Link to="/requests">همه</Link>}>
          {reqLoading && !requests ? <LoadingBlock /> : !pendingTeam.length ? <p>درخواستی در صف نیست.</p> : (
            <ul className="list">
              {pendingTeam.slice(0, 6).map((r) => (
                <li key={r.id}>
                  <Link to={`/requests/${r.id}`}>{r.employeeName} · {formatRequestRange(r)}{r.durationKind === "hourly" && <span className="kind-tag">ساعتی</span>}</Link>
                  <span className="toolbar" style={{ margin: 0 }}>
                    <DeadlineLabel hideEmpty info={deadlineInfo(r, todayIso())} />
                    <StatusBadge status={r.status} />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {hasAny(roles, "employee") && !isAdmin && (
        <div className={isApprover ? "mt" : undefined}>
          <Card title="آخرین درخواست‌های من" actions={<Link to="/requests">مشاهده</Link>}>
            {reqLoading && !requests ? <LoadingBlock /> : !mine.length ? <p>هنوز درخواستی ثبت نشده.</p> : (
              <ul className="list">
                {mine.slice(0, 5).map((r) => (
                  <li key={r.id}>
                    <Link to={`/requests/${r.id}`}>{r.typeLabel ?? "مرخصی"} · {formatRequestRange(r, true)}</Link>
                    <span className="toolbar" style={{ margin: 0 }}>
                      <DeadlineLabel hideEmpty info={deadlineInfo(r, todayIso())} />
                      <StatusBadge status={r.status} />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
      <div className="toolbar mt">
        <Link to="/calendar" className="btn secondary sm">تقویم</Link>
        {isRequester && <Link to="/balances" className="btn secondary sm">مانده</Link>}
        {hasAny(roles, "hr") && <Link to="/hr/absences" className="btn secondary sm">ثبت غیبت HR</Link>}
        {isAdmin && <Link to="/settings" className="btn secondary sm">تنظیمات</Link>}
      </div>
    </>
  );
}
