import datetime as dt
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from leave.entitlement_services import create_entitlement, entitlement_balance
from leave.job_services import (
    JOB_HANDLERS,
    JobResult,
    _run_carry_forward,
    _run_expiration,
    _run_manager_reminders,
    _run_overdue_escalations,
    _schedule_for,
    _scheduled_local_datetime,
    execute_job,
    job_status_payload,
    run_due_jobs,
)
from leave.models import (
    AuditEvent,
    Company,
    EntitlementEvent,
    EmployeeProfile,
    JobEffect,
    JobExecution,
    LeaveEntitlement,
    LeavePolicyVersion,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveType,
    SchedulerHeartbeat,
    SystemSetting,
)
from zsh_core import settings_schema, workflow as wf
from zsh_core.policy import leave_year_of


class ScheduledJobTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_superuser(
            username="jobs-admin", email="jobs-admin@example.test", password="not-used",
        )
        self.user = user_model.objects.create_user(username="jobs-employee")
        self.manager_user = user_model.objects.create_user(username="jobs-manager")
        self.company = Company.objects.create(code="JOBS", name="Jobs")
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user,
            company=self.company,
            personnel_code="M-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.user,
            company=self.company,
            personnel_code="E-1",
            manager=self.manager,
            start_date=dt.date(2020, 1, 1),
        )
        self.leave_type = LeaveType.objects.create(
            key="jobs-annual", label_fa="استحقاقی", counts_against_balance=True,
        )
        self.scheduled_for = dt.datetime(
            2026, 11, 1, 10, 0, tzinfo=ZoneInfo("Asia/Tehran"),
        )

    def request(self):
        return LeaveRequest.objects.create(
            employee=self.employee,
            manager_snapshot=self.manager,
            leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 2),
            end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"),
            status=wf.PENDING,
        )

    def set_setting(self, key, value):
        SystemSetting.objects.update_or_create(key=key, defaults={"value": value})

    def test_job_schedule_due_time_and_timezone_boundary(self):
        tz = ZoneInfo("Asia/Tehran")
        before = dt.datetime(2026, 11, 1, 0, 14, tzinfo=tz)
        after = dt.datetime(2026, 11, 1, 0, 16, tzinfo=tz)
        self.assertIsNone(_schedule_for("carry_forward", before))
        self.assertEqual(_schedule_for("carry_forward", after).time(), dt.time(0, 15))

        with override_settings(TIME_ZONE="America/New_York"):
            timezone.activate("America/New_York")
            try:
                # The UTC instant is after the spring-forward gap in New York.
                instant = dt.datetime(2026, 3, 8, 7, 10, tzinfo=dt.timezone.utc)
                due = _schedule_for("manager_reminders", instant)
                self.assertEqual((due.hour, due.minute, due.utcoffset()), (
                    3, 10, dt.timedelta(hours=-4),
                ))
                second_fold = dt.datetime(2026, 11, 1, 6, 10, tzinfo=dt.timezone.utc)
                due_fold = _schedule_for("manager_reminders", second_fold)
                self.assertEqual((due_fold.hour, due_fold.minute, due_fold.fold), (1, 10, 0))
                shifted = _scheduled_local_datetime(
                    dt.date(2026, 3, 8), dt.time(2, 15),
                )
                self.assertEqual((shifted.hour, shifted.minute), (3, 0))
            finally:
                timezone.deactivate()

    def test_successful_execution_is_idempotent_for_a_schedule_slot(self):
        handler = Mock(return_value=JobResult({"processed": 2}))
        with patch.dict(JOB_HANDLERS, {"manager_reminders": handler}):
            first = execute_job("manager_reminders", self.scheduled_for)
            replay = execute_job("manager_reminders", self.scheduled_for)

        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(first.status, JobExecution.STATUS_SUCCEEDED)
        self.assertEqual(first.attempt_count, 1)
        handler.assert_called_once_with()

    def test_due_dispatch_skips_before_daily_time_and_runs_once_when_due(self):
        self.set_setting("jobs.carry_forward_policy", "unlimited")
        before = dt.datetime(2026, 11, 1, 0, 14, tzinfo=ZoneInfo("Asia/Tehran"))
        due = dt.datetime(2026, 11, 1, 0, 16, tzinfo=ZoneInfo("Asia/Tehran"))
        handler = Mock(return_value=JobResult({"processed": 0}))
        with patch.dict(JOB_HANDLERS, {"carry_forward": handler}):
            self.assertEqual(run_due_jobs(before), [])
            first = run_due_jobs(due)
            replay = run_due_jobs(due)

        self.assertEqual([item.job_name for item in first], ["carry_forward"])
        self.assertEqual(first[0].pk, replay[0].pk)
        local_scheduled_for = timezone.localtime(
            first[0].scheduled_for, ZoneInfo("Asia/Tehran"),
        )
        self.assertEqual(local_scheduled_for.time(), dt.time(0, 15))
        handler.assert_called_once_with()

    def test_transient_failure_retries_after_backoff(self):
        handler = Mock(side_effect=[
            ConnectionError("private connection detail"),
            JobResult({"processed": 1}),
        ])
        with patch.dict(JOB_HANDLERS, {"manager_reminders": handler}):
            first = execute_job(
                "manager_reminders", self.scheduled_for,
                now=self.scheduled_for,
            )
            early = execute_job(
                "manager_reminders", self.scheduled_for,
                now=self.scheduled_for + dt.timedelta(minutes=4),
            )
            retried = execute_job(
                "manager_reminders", self.scheduled_for,
                now=self.scheduled_for + dt.timedelta(minutes=5),
            )

        self.assertEqual(first.status, JobExecution.STATUS_FAILED)
        self.assertEqual(first.error_code, "ConnectionError")
        self.assertNotIn("private", str(first.result_summary))
        self.assertEqual(early.attempt_count, 1)
        self.assertEqual(retried.status, JobExecution.STATUS_SUCCEEDED)
        self.assertEqual(retried.attempt_count, 2)
        self.assertEqual(handler.call_count, 2)

    def test_permanent_failure_is_not_retried(self):
        handler = Mock(side_effect=ValueError("validation detail"))
        with patch.dict(JOB_HANDLERS, {"manager_reminders": handler}):
            first = execute_job("manager_reminders", self.scheduled_for)
            replay = execute_job("manager_reminders", self.scheduled_for)

        self.assertEqual(first.status, JobExecution.STATUS_FAILED)
        self.assertIsNone(first.retry_after)
        self.assertEqual(replay.attempt_count, 1)
        handler.assert_called_once_with()

    def test_batch_partial_failure_is_visible_without_sensitive_error_text(self):
        first_request = self.request()
        second_request = self.request()
        self.set_setting("workflow.reminder_after_working_days", 1)
        with patch(
            "leave.job_services._working_days_since",
            side_effect=[ValueError("private employee data"), Decimal("2")],
        ):
            result = _run_manager_reminders()

        self.assertTrue(result.partial_failure)
        self.assertEqual(result.summary["permanentFailureCount"], 1)
        self.assertEqual(result.summary["failureCodes"], ["ValueError"])
        self.assertEqual(
            LeaveRequestEvent.objects.filter(event="reminder").count(),
            1,
        )
        self.assertEqual(JobEffect.objects.count(), 1)
        self.assertNotIn("private employee data", str(result.summary))
        self.assertTrue(first_request.pk)
        self.assertTrue(second_request.pk)

    def test_carry_forward_and_expiration_do_not_duplicate_ledger_events(self):
        today = timezone.localdate()
        values = {
            key: settings_schema.to_storable(value)
            for key, value in settings_schema.defaults().items()
            if key.startswith("policy.")
        }
        LeavePolicyVersion.objects.create(
            scope="organization",
            version=1,
            effective_from=today,
            values=values,
            reason="job test policy",
        )
        current_year = leave_year_of(today, settings_schema.build_policy({}))
        previous = create_entitlement(
            employee=self.employee,
            leave_type=self.leave_type,
            year=current_year - 1,
            base_days=Decimal("10"),
            carry_over_days=Decimal("3"),
            reason="opening",
            idempotency_key="jobs-opening",
        )
        self.set_setting("jobs.expire_carry_over", True)
        self.set_setting("jobs.carry_forward_policy", "unlimited")

        _run_expiration()
        _run_expiration()
        _run_carry_forward()
        _run_carry_forward()

        previous.refresh_from_db()
        target = LeaveEntitlement.objects.get(
            employee=self.employee, leave_type=self.leave_type, year=current_year,
        )
        self.assertEqual(previous.carry_over_days, Decimal("0.0"))
        self.assertEqual(entitlement_balance(target)["total"], Decimal("10.0"))
        self.assertEqual(
            EntitlementEvent.objects.filter(entitlement=previous, kind="expiration").count(),
            1,
        )
        self.assertEqual(
            EntitlementEvent.objects.filter(
                entitlement=target, kind="carry_forward",
            ).count(),
            1,
        )

    def test_escalation_is_idempotent_and_audited(self):
        request = self.request()
        self.set_setting("workflow.escalate_after_working_days", 1)
        with patch("leave.job_services._working_days_since", return_value=Decimal("2")):
            _run_overdue_escalations()
            _run_overdue_escalations()

        request.refresh_from_db()
        self.assertEqual(request.status, wf.ESCALATED)
        self.assertEqual(
            LeaveRequestEvent.objects.filter(request=request, event="escalate").count(),
            1,
        )
        self.assertEqual(
            AuditEvent.objects.filter(entity="LeaveRequest", entity_id=str(request.pk)).count(),
            1,
        )

    def test_jobs_api_is_admin_only_redacted_and_has_no_manual_run(self):
        execution = JobExecution.objects.create(
            job_name="manager_reminders",
            scheduled_for=self.scheduled_for,
            status=JobExecution.STATUS_FAILED,
            attempt_count=1,
            error_code="ValidationError",
            result_summary={"retryable": False, "employeeName": "Sensitive Employee"},
        )
        client = APIClient()
        client.force_authenticate(self.user)
        self.assertEqual(client.get("/api/v1/admin/jobs/").status_code, 403)

        client.force_authenticate(self.admin)
        response = client.get("/api/v1/admin/jobs/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["scheduler"]["status"], "scheduler_not_configured")
        row = next(item for item in payload["jobs"] if item["name"] == "manager_reminders")
        self.assertEqual(row["lastExecution"]["errorCode"], "ValidationError")
        self.assertEqual(row["lastExecution"]["resultSummary"], {"retryable": False})
        self.assertNotIn("traceback", str(payload).lower())
        self.assertNotIn(self.user.username, str(payload))
        self.assertEqual(client.post("/api/v1/admin/jobs/").status_code, 405)
        self.assertEqual(str(execution.correlation_id), row["lastExecution"]["correlationId"])

    @override_settings(ZSH_JOB_SCHEDULER_ENABLED=True)
    def test_scheduler_heartbeat_health_and_staleness(self):
        self.assertEqual(job_status_payload()["scheduler"]["status"], "waiting_for_first_heartbeat")
        SchedulerHeartbeat.objects.create(
            name="periodic", checked_at=timezone.now() - dt.timedelta(minutes=16),
        )
        self.assertEqual(job_status_payload()["scheduler"]["status"], "stale")

    @override_settings(
        ZSH_JOB_SCHEDULER_ENABLED=True,
        ZSH_JOB_SCHEDULER_REQUIRED=True,
    )
    def test_readiness_requires_a_fresh_scheduler_heartbeat_when_enabled(self):
        client = APIClient()
        self.assertEqual(client.get("/api/v1/ready/").status_code, 503)
        SchedulerHeartbeat.objects.create(name="periodic", checked_at=timezone.now())
        self.assertEqual(client.get("/api/v1/ready/").status_code, 200)

    def test_management_command_requires_explicit_local_enablement(self):
        with override_settings(DEBUG=False, ZSH_JOB_SCHEDULER_ENABLED=False):
            with self.assertRaises(CommandError):
                call_command("run_scheduled_jobs")

        with (
            override_settings(DEBUG=True, ZSH_JOB_SCHEDULER_ENABLED=False),
            patch("leave.management.commands.run_scheduled_jobs.run_due_jobs", return_value=[]),
        ):
            call_command("run_scheduled_jobs", enable_local=True, stdout=Mock())
        self.assertTrue(SchedulerHeartbeat.objects.filter(name="periodic").exists())


class ConcurrentJobExecutionTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_same_slot_executes_once(self):
        scheduled_for = dt.datetime(
            2026, 11, 1, 10, 0, tzinfo=ZoneInfo("Asia/Tehran"),
        )
        barrier = threading.Barrier(2)
        handler_started = threading.Event()
        allow_handler_finish = threading.Event()
        call_count = []
        call_count_lock = threading.Lock()

        def handler():
            with call_count_lock:
                call_count.append(1)
            handler_started.set()
            if not allow_handler_finish.wait(timeout=5):
                raise TimeoutError("test handler was not released")
            return JobResult({"processed": 1})

        def run():
            close_old_connections()
            barrier.wait(timeout=5)
            try:
                return execute_job("manager_reminders", scheduled_for)
            finally:
                close_old_connections()

        with patch.dict(JOB_HANDLERS, {"manager_reminders": handler}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(run) for _ in range(2)]
                self.assertTrue(handler_started.wait(timeout=5))
                running = JobExecution.objects.get(job_name="manager_reminders")
                self.assertEqual(running.status, JobExecution.STATUS_RUNNING)
                self.assertIsNotNone(running.started_at)
                self.assertEqual(running.attempt_count, 1)
                allow_handler_finish.set()
                results = [future.result(timeout=5) for future in futures]

        self.assertEqual(results[0].pk, results[1].pk)
        self.assertEqual(call_count, [1])
        self.assertEqual(
            JobExecution.objects.filter(job_name="manager_reminders").count(),
            1,
        )
