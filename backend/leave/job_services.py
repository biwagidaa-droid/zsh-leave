from __future__ import annotations

import datetime as dt
import hashlib
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, IntegrityError, InterfaceError, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone

from zsh_core import settings_schema, workflow as wf
from zsh_core.policy import leave_year_of
from . import audit_services
from .calendar_services import CalendarConfigurationError, calculate_working_days, policy_from_version, resolve_policy_version
from .employment_services import employees_employed_on
from .entitlement_services import (
    EntitlementLedgerError,
    carry_forward,
    entitlement_event_idempotency_key,
    expire_carry_over,
)
from .middleware import audit_context
from .models import (
    EmployeeProfile,
    EntitlementEvent,
    JobEffect,
    JobExecution,
    LeaveEntitlement,
    LeaveRequest,
    LeaveRequestEvent,
    NotificationDelivery,
    SchedulerHeartbeat,
    SystemSetting,
)
from .services import escalate_overdue
from .notification_services import deliver_pending_notifications, queue_request_event_delivery

logger = logging.getLogger(__name__)

SCHEDULER_HEARTBEAT_NAME = "periodic"
SCHEDULER_STALE_AFTER = dt.timedelta(minutes=15)
MAX_ATTEMPTS = 3
RETRY_DELAYS = (dt.timedelta(minutes=5), dt.timedelta(minutes=15))
REMINDER_EFFECT_PREFIX = "leave-request-reminder:"
_local_execution_locks: dict[str, threading.Lock] = {}
_local_execution_locks_guard = threading.Lock()


@dataclass(frozen=True)
class JobResult:
    summary: dict
    partial_failure: bool = False


class TransientJobError(Exception):
    pass


def _settings_values() -> dict:
    overrides = dict(SystemSetting.objects.values_list("key", "value"))
    return settings_schema.resolve(overrides)


def scheduler_state(now: dt.datetime | None = None) -> dict:
    now = now or timezone.now()
    if not settings.ZSH_JOB_SCHEDULER_ENABLED:
        return {"status": "scheduler_not_configured", "lastHeartbeat": None}
    heartbeat = SchedulerHeartbeat.objects.filter(name=SCHEDULER_HEARTBEAT_NAME).first()
    if heartbeat is None:
        return {"status": "waiting_for_first_heartbeat", "lastHeartbeat": None}
    stale = heartbeat.checked_at < now - SCHEDULER_STALE_AFTER
    return {
        "status": "stale" if stale else "healthy",
        "lastHeartbeat": heartbeat.checked_at.isoformat(),
    }


def record_scheduler_heartbeat(now: dt.datetime | None = None) -> None:
    SchedulerHeartbeat.objects.update_or_create(
        name=SCHEDULER_HEARTBEAT_NAME,
        defaults={"checked_at": now or timezone.now()},
    )


def _schedule_for(job_name: str, now: dt.datetime) -> dt.datetime | None:
    local_now = timezone.localtime(now, timezone.get_default_timezone())
    if job_name in {"overdue_escalation", "manager_reminders", "notification_delivery"}:
        minute = local_now.minute - local_now.minute % 5
        local_schedule = _scheduled_local_datetime(
            local_now.date(), dt.time(local_now.hour, minute),
        )
    else:
        local_schedule = _scheduled_local_datetime(local_now.date(), dt.time(0, 15))
        if local_now < local_schedule:
            return None
    return local_schedule


def _scheduled_local_datetime(day: dt.date, wall_time: dt.time) -> dt.datetime:
    zone = timezone.get_default_timezone()
    naive = dt.datetime.combine(day, wall_time.replace(tzinfo=None))
    for minutes_after in range(181):
        candidate_naive = naive + dt.timedelta(minutes=minutes_after)
        candidate = candidate_naive.replace(tzinfo=zone, fold=0)
        round_trip = candidate.astimezone(dt.timezone.utc).astimezone(zone)
        if round_trip.replace(tzinfo=None) == candidate_naive:
            return candidate
    raise ValueError("No valid local scheduler time within three hours")


def _working_days_since(request: LeaveRequest, today: dt.date) -> Decimal:
    organization_tz = timezone.get_default_timezone()
    created_date = timezone.localtime(request.created_at, organization_tz).date()
    start = created_date + dt.timedelta(days=1)
    if start > today:
        return Decimal("0")
    return calculate_working_days(
        employee=request.employee,
        start=start,
        end=today,
        policy_version=request.policy_version,
    ).days


def _run_threshold_job(job_name: str, setting_key: str, event_name: str | None = None) -> JobResult:
    threshold = _settings_values()[setting_key]
    if threshold is None:
        return JobResult({"disabled": "threshold_not_configured", "processed": 0})

    today = timezone.localdate()
    processed = 0
    failures: list[str] = []
    requests = LeaveRequest.objects.filter(status=wf.PENDING).select_related(
        "employee", "leave_type", "policy_version",
    ).order_by("pk")
    if event_name:
        requests = requests.filter(manager_snapshot__isnull=False)
    for request in requests.iterator():
        try:
            if _working_days_since(request, today) < threshold:
                continue
            if event_name is None:
                processed += escalate_overdue([request.pk])
                continue

            with transaction.atomic():
                current_request = LeaveRequest.objects.select_for_update().filter(
                    pk=request.pk,
                    status=wf.PENDING,
                    manager_snapshot__isnull=False,
                ).first()
                if current_request is None:
                    continue
                effect_key = f"{REMINDER_EFFECT_PREFIX}{current_request.pk}"
                _, created = JobEffect.objects.get_or_create(
                    effect_key=effect_key,
                    defaults={"job_name": job_name},
                )
                if not created:
                    continue
                event = LeaveRequestEvent.objects.create(
                    request=current_request,
                    actor=None,
                    origin=wf.SYSTEM,
                    event=event_name,
                    from_status=current_request.status,
                    to_status=current_request.status,
                )
                queue_request_event_delivery(event)
                audit_services.record_audit(
                    actor=None,
                    origin=wf.SYSTEM,
                    action="leave.reminder",
                    entity="LeaveRequestEvent",
                    entity_id=event.pk,
                    before={"status": current_request.status},
                    after={"status": current_request.status, "event": event_name},
                )
            processed += 1
        except (OperationalError, InterfaceError, TimeoutError, ConnectionError) as exc:
            raise TransientJobError(type(exc).__name__) from exc
        except (ValidationError, CalendarConfigurationError, EntitlementLedgerError, ValueError) as exc:
            code = type(exc).__name__
            failures.append(code)
            logger.warning("job item failed job=%s error_code=%s", job_name, code)

    return JobResult({
        "processed": processed,
        "permanentFailureCount": len(failures),
        "failureCodes": sorted(set(failures)),
    }, partial_failure=bool(failures))


def _policy_for(employee: EmployeeProfile, today: dt.date):
    return policy_from_version(resolve_policy_version(employee, today))


def _run_entitlement_rollover(*, expire: bool) -> JobResult:
    options = _settings_values()
    carry_policy = options["jobs.carry_forward_policy"]
    cap = options["jobs.carry_forward_cap"]
    if expire and not options["jobs.expire_carry_over"]:
        return JobResult({"disabled": "expiration_not_configured", "processed": 0})
    if not expire and carry_policy == "none":
        return JobResult({"disabled": "carry_forward_policy_none", "processed": 0})
    if not expire and carry_policy == "capped" and cap is None:
        raise settings_schema.SettingError("carry_forward_cap_required")

    today = timezone.localdate()
    processed = 0
    failures: list[str] = []
    employees = employees_employed_on(
        EmployeeProfile.objects.select_related("company", "site", "department"),
        today,
    ).order_by("pk")
    for employee in employees.iterator():
        try:
            policy = _policy_for(employee, today)
            current_year = leave_year_of(today, policy)
            previous_rows = LeaveEntitlement.objects.filter(
                employee=employee, year=current_year - 1,
            ).order_by("pk")
            for previous in previous_rows.iterator():
                if expire:
                    event_key = f"scheduled-expiration:{current_year}"
                    prior = EntitlementEvent.objects.filter(
                        entitlement=previous,
                        kind="expiration",
                        idempotency_key=entitlement_event_idempotency_key(previous.pk, event_key),
                    ).exists()
                    if prior:
                        continue
                    expire_carry_over(
                        entitlement_id=previous.pk,
                        actor=None,
                        reason=f"Automatic expiry at leave-year {current_year} boundary",
                        idempotency_key=event_key,
                    )
                else:
                    carry_forward(
                        previous_entitlement_id=previous.pk,
                        next_year=current_year,
                        policy=carry_policy,
                        cap=cap if carry_policy == "capped" else None,
                        actor=None,
                        reason=f"Automatic carry-forward into leave-year {current_year}",
                        idempotency_key=f"scheduled-carry-forward:{current_year}",
                    )
                processed += 1
        except (OperationalError, InterfaceError, TimeoutError, ConnectionError) as exc:
            raise TransientJobError(type(exc).__name__) from exc
        except (
            ValidationError, CalendarConfigurationError, EntitlementLedgerError, ValueError,
        ) as exc:
            code = type(exc).__name__
            failures.append(code)
            logger.warning("job item failed job=%s error_code=%s", (
                "entitlement_expiration" if expire else "carry_forward"
            ), code)

    return JobResult({
        "processed": processed,
        "permanentFailureCount": len(failures),
        "failureCodes": sorted(set(failures)),
    }, partial_failure=bool(failures))


def _run_overdue_escalations() -> JobResult:
    return _run_threshold_job(
        "overdue_escalation", "workflow.escalate_after_working_days",
    )


def _run_manager_reminders() -> JobResult:
    return _run_threshold_job(
        "manager_reminders", "workflow.reminder_after_working_days", event_name="reminder",
    )


def _run_notification_delivery() -> JobResult:
    return JobResult(deliver_pending_notifications())


def _run_carry_forward() -> JobResult:
    return _run_entitlement_rollover(expire=False)


def _run_expiration() -> JobResult:
    return _run_entitlement_rollover(expire=True)


JOB_HANDLERS = {
    "overdue_escalation": _run_overdue_escalations,
    "manager_reminders": _run_manager_reminders,
    "notification_delivery": _run_notification_delivery,
    "entitlement_expiration": _run_expiration,
    "carry_forward": _run_carry_forward,
}

JOB_METADATA = {
    "overdue_escalation": {
        "schedule": "هر ۵ دقیقه؛ پس از رسیدن به آستانه روز کاری",
        "purpose": "ارجاع درخواست‌های معوق از مسیر سرویس گردش‌کار",
    },
    "manager_reminders": {
        "schedule": "هر ۵ دقیقه؛ پس از رسیدن به آستانه روز کاری",
        "purpose": "ثبت یک اعلان درون‌برنامه‌ای برای مدیر درخواست معوق",
    },
    "notification_delivery": {
        "schedule": "هر ۵ دقیقه، در صورت وجود اعلان ایمیل صف‌شده",
        "purpose": "ارسال ایمیل‌های صف‌شده با تلاش مجدد محدود",
    },
    "carry_forward": {
        "schedule": "روزانه ساعت ۰۰:۱۵",
        "purpose": "انتقال سهمیه قابل استفاده به سال مرخصی جاری",
    },
    "entitlement_expiration": {
        "schedule": "روزانه ساعت ۰۰:۱۵، پیش از انتقال مانده",
        "purpose": "انقضای مؤلفه انتقال‌یافته سال مرخصی قبل",
    },
}


def _thread_lock(job_name: str) -> threading.Lock:
    with _local_execution_locks_guard:
        return _local_execution_locks.setdefault(job_name, threading.Lock())


@contextmanager
def _execution_lock(lock_name: str):
    acquired = False
    lock_key = int.from_bytes(
        hashlib.sha256(lock_name.encode("utf-8")).digest()[:8],
        byteorder="big",
        signed=True,
    )
    try:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_key])
                acquired = cursor.fetchone()[0]
        else:
            acquired = True
        yield acquired
    finally:
        if acquired and connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])


def _transient_error(error: Exception) -> bool:
    return isinstance(
        error,
        (TransientJobError, OperationalError, InterfaceError, TimeoutError, ConnectionError),
    )


def execute_job(
    job_name: str,
    scheduled_for: dt.datetime,
    *,
    now: dt.datetime | None = None,
) -> JobExecution:
    if job_name not in JOB_HANDLERS:
        raise ValueError(f"Unknown scheduled job: {job_name}")
    now = now or timezone.now()
    if timezone.is_naive(scheduled_for) or timezone.is_naive(now):
        raise ValueError("Scheduled and current timestamps must be timezone-aware")
    scheduled_for = scheduled_for.astimezone(timezone.get_default_timezone())
    lock_name = (
        "entitlement_rollover"
        if job_name in {"entitlement_expiration", "carry_forward"}
        else job_name
    )

    with _thread_lock(lock_name):
        try:
            with transaction.atomic():
                execution = JobExecution.objects.create(
                    job_name=job_name,
                    scheduled_for=scheduled_for,
                    correlation_id=str(uuid4()),
                )
        except IntegrityError:
            execution = JobExecution.objects.get(
                job_name=job_name, scheduled_for=scheduled_for,
            )

        with _execution_lock(lock_name) as acquired:
            if not acquired:
                return JobExecution.objects.get(pk=execution.pk)
            execution, should_run = _claim_execution(execution.pk, now=now)
            if not should_run:
                return execution

            try:
                with audit_context(
                    correlation_id=execution.correlation_id,
                    source=f"job:{execution.job_name}",
                ):
                    result = JOB_HANDLERS[execution.job_name]()
            except Exception as exc:
                return _finish_failure(execution.pk, error=exc, now=now)
            return _finish_success(execution.pk, result=result, now=now)


@transaction.atomic
def _claim_execution(execution_id: int, *, now: dt.datetime) -> tuple[JobExecution, bool]:
    execution = JobExecution.objects.select_for_update().get(pk=execution_id)
    if execution.status in {
        JobExecution.STATUS_SUCCEEDED,
        JobExecution.STATUS_PARTIAL_FAILURE,
    }:
        return execution, False
    if execution.status == JobExecution.STATUS_FAILED:
        if execution.retry_after is None or execution.retry_after > now:
            return execution, False
    if execution.status == JobExecution.STATUS_RUNNING:
        if (
            execution.started_at is not None
            and execution.started_at > now - SCHEDULER_STALE_AFTER
        ):
            return execution, False
        if execution.attempt_count >= MAX_ATTEMPTS:
            execution.status = JobExecution.STATUS_FAILED
            execution.error_code = "WorkerLeaseExpired"
            execution.result_summary = {"retryable": False}
            execution.completed_at = now
            execution.save(update_fields=[
                "status", "error_code", "result_summary", "completed_at",
            ])
            return execution, False
    if execution.attempt_count >= MAX_ATTEMPTS:
        return execution, False

    execution.status = JobExecution.STATUS_RUNNING
    execution.attempt_count += 1
    execution.started_at = now
    execution.completed_at = None
    execution.retry_after = None
    execution.error_code = ""
    execution.save(update_fields=[
        "status", "attempt_count", "started_at", "completed_at", "retry_after", "error_code",
    ])
    return execution, True


@transaction.atomic
def _finish_failure(
    execution_id: int,
    *,
    error: Exception,
    now: dt.datetime,
) -> JobExecution:
    execution = JobExecution.objects.select_for_update().get(pk=execution_id)
    execution.status = JobExecution.STATUS_FAILED
    execution.error_code = type(error).__name__[:64]
    retryable = _transient_error(error)
    execution.result_summary = {"retryable": retryable}
    if retryable and execution.attempt_count < MAX_ATTEMPTS:
        execution.retry_after = now + RETRY_DELAYS[execution.attempt_count - 1]
    execution.completed_at = now
    execution.save(update_fields=[
        "status", "error_code", "result_summary", "retry_after", "completed_at",
    ])
    logger.error(
        "job execution failed job=%s correlation_id=%s error_code=%s retryable=%s",
        execution.job_name, execution.correlation_id, execution.error_code, retryable,
    )
    return execution


@transaction.atomic
def _finish_success(
    execution_id: int,
    *,
    result: JobResult,
    now: dt.datetime,
) -> JobExecution:
    execution = JobExecution.objects.select_for_update().get(pk=execution_id)
    execution.status = (
        JobExecution.STATUS_PARTIAL_FAILURE
        if result.partial_failure else JobExecution.STATUS_SUCCEEDED
    )
    execution.result_summary = result.summary
    execution.completed_at = now
    execution.save(update_fields=[
        "status", "result_summary", "completed_at",
    ])
    return execution


def run_due_jobs(now: dt.datetime | None = None) -> list[JobExecution]:
    now = now or timezone.now()
    options = _settings_values()
    enabled = {
        "overdue_escalation": options["workflow.escalate_after_working_days"] is not None,
        "manager_reminders": options["workflow.reminder_after_working_days"] is not None,
        "notification_delivery": NotificationDelivery.objects.filter(
            Q(status__in=[
                NotificationDelivery.STATUS_QUEUED,
                NotificationDelivery.STATUS_SENDING,
            ])
            | Q(
                status=NotificationDelivery.STATUS_UNAVAILABLE,
                last_error_code="EmailProviderNotConfigured",
            ),
        ).exists(),
        "entitlement_expiration": options["jobs.expire_carry_over"],
        "carry_forward": (
            options["jobs.carry_forward_policy"] != "none"
            and (
                options["jobs.carry_forward_policy"] != "capped"
                or options["jobs.carry_forward_cap"] is not None
            )
        ),
    }
    results = []
    for job_name in JOB_HANDLERS:
        if not enabled[job_name]:
            continue
        pending_times = set()
        pending_rows = JobExecution.objects.filter(
            job_name=job_name,
            status__in=[JobExecution.STATUS_QUEUED, JobExecution.STATUS_RUNNING],
        ).order_by("scheduled_for")
        for pending in pending_rows:
            pending_times.add(pending.scheduled_for)
            results.append(execute_job(job_name, pending.scheduled_for, now=now))
        retry_rows = JobExecution.objects.filter(
            job_name=job_name,
            status=JobExecution.STATUS_FAILED,
            retry_after__lte=now,
            attempt_count__lt=MAX_ATTEMPTS,
        ).order_by("retry_after", "scheduled_for")
        for retry in retry_rows:
            results.append(execute_job(job_name, retry.scheduled_for, now=now))
        if JobExecution.objects.filter(
            job_name=job_name,
            status=JobExecution.STATUS_FAILED,
            retry_after__gt=now,
            attempt_count__lt=MAX_ATTEMPTS,
        ).exists():
            continue
        scheduled_for = _schedule_for(job_name, now)
        if scheduled_for is None or scheduled_for in pending_times or any(
            item.job_name == job_name and item.scheduled_for == scheduled_for for item in results
        ):
            continue
        results.append(execute_job(job_name, scheduled_for, now=now))
    return results


def job_status_payload(now: dt.datetime | None = None) -> dict:
    from django.conf import settings

    now = now or timezone.now()
    state = scheduler_state(now)
    if not settings.ZSH_JOB_SCHEDULER_ENABLED:
        state["configured"] = False
    else:
        state["configured"] = state["status"] == "healthy"

    options = _settings_values()
    jobs = []
    for name, metadata in JOB_METADATA.items():
        execution = JobExecution.objects.filter(job_name=name).order_by(
            "-scheduled_for", "-pk",
        ).first()
        enabled, disabled_reason = {
            "overdue_escalation": (
                options["workflow.escalate_after_working_days"] is not None,
                "threshold_not_configured",
            ),
            "manager_reminders": (
                options["workflow.reminder_after_working_days"] is not None,
                "threshold_not_configured",
            ),
            "notification_delivery": (
                NotificationDelivery.objects.filter(
                    Q(status__in=[
                        NotificationDelivery.STATUS_QUEUED,
                        NotificationDelivery.STATUS_SENDING,
                    ])
                    | Q(
                        status=NotificationDelivery.STATUS_UNAVAILABLE,
                        last_error_code="EmailProviderNotConfigured",
                    ),
                ).exists(),
                "no_pending_deliveries",
            ),
            "carry_forward": (
                options["jobs.carry_forward_policy"] != "none"
                and (
                    options["jobs.carry_forward_policy"] != "capped"
                    or options["jobs.carry_forward_cap"] is not None
                ),
                (
                    "carry_forward_cap_required"
                    if options["jobs.carry_forward_policy"] == "capped"
                    and options["jobs.carry_forward_cap"] is None
                    else "carry_forward_policy_none"
                ),
            ),
            "entitlement_expiration": (
                options["jobs.expire_carry_over"],
                "expiration_not_configured",
            ),
        }[name]
        jobs.append({
            "name": name,
            **metadata,
            "enabled": enabled,
            "disabledReason": None if enabled else disabled_reason,
            "timezone": timezone.get_default_timezone_name(),
            "lastExecution": _execution_payload(execution) if execution else None,
        })
    return {"scheduler": state, "jobs": jobs}


def _execution_payload(execution: JobExecution) -> dict:
    summary = execution.result_summary if isinstance(execution.result_summary, dict) else {}
    safe_summary = {}
    for key in ("processed", "permanentFailureCount"):
        value = summary.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            safe_summary[key] = value
    failure_codes = summary.get("failureCodes")
    if isinstance(failure_codes, list):
        safe_summary["failureCodes"] = [
            code for code in failure_codes
            if isinstance(code, str) and code.isascii() and code.isidentifier()
        ][:20]
    disabled = summary.get("disabled")
    if isinstance(disabled, str) and disabled.isascii() and disabled.isidentifier():
        safe_summary["disabled"] = disabled
    retryable = summary.get("retryable")
    if isinstance(retryable, bool):
        safe_summary["retryable"] = retryable
    error_code = execution.error_code
    if not error_code.isascii() or not error_code.isidentifier():
        error_code = "JobError" if error_code else ""
    return {
        "scheduledFor": execution.scheduled_for.isoformat(),
        "startedAt": execution.started_at.isoformat() if execution.started_at else None,
        "completedAt": execution.completed_at.isoformat() if execution.completed_at else None,
        "status": execution.status,
        "attemptCount": execution.attempt_count,
        "resultSummary": safe_summary,
        "errorCode": error_code or None,
        "retryAfter": execution.retry_after.isoformat() if execution.retry_after else None,
        "correlationId": execution.correlation_id,
    }
