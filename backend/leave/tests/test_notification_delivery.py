import datetime as dt
from datetime import timedelta
from decimal import Decimal
from io import StringIO
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from leave.job_services import execute_job, run_due_jobs
from leave.entitlement_services import create_entitlement
from leave.models import (
    Company,
    EmployeeProfile,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveType,
    NotificationDelivery,
    RoleAssignment,
    SystemSetting,
)
from leave.notification_services import (
    EmailProviderError,
    DjangoEmailProvider,
    deliver_pending_notifications,
    queue_request_event_delivery,
)
from leave.services import _log


class NotificationDeliveryTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        user_model = get_user_model()
        self.company = Company.objects.create(code="NOTIFY", name="Notifications")
        self.employee_user = user_model.objects.create_user(
            username="notify-employee", email="employee@example.test",
        )
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            company=self.company,
            personnel_code="N-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.manager_user = user_model.objects.create_user(
            username="notify-manager", email="manager@example.test",
        )
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user,
            company=self.company,
            personnel_code="N-M1",
            start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = self.manager
        self.employee.save(update_fields=["manager"])
        self.leave_type = LeaveType.objects.create(
            key="notify-annual", label_fa="Leave type confidential label",
            counts_against_balance=True,
        )
        self.request = LeaveRequest.objects.create(
            employee=self.employee,
            manager_snapshot=self.manager,
            leave_type=self.leave_type,
            start_date=dt.date(2026, 11, 2),
            end_date=dt.date(2026, 11, 2),
            working_days="1.0",
            status="PENDING",
            reason="Sensitive reason that must not be mailed",
        )
        self.event = LeaveRequestEvent.objects.create(
            request=self.request,
            actor=self.manager_user,
            origin="manager",
            event="approve",
            from_status="PENDING",
            to_status="APPROVED",
            reason="Sensitive decision details",
        )

    def queue_employee_delivery(self):
        queue_request_event_delivery(self.event)
        return NotificationDelivery.objects.get(
            idempotency_key=f"request-event:{self.event.pk}:user:{self.employee_user.pk}",
        )

    def test_request_event_logger_queues_manager_delivery(self):
        _log(
            self.request, self.employee_user, "employee", "submit", "", "PENDING",
        )
        event = LeaveRequestEvent.objects.get(
            request=self.request, actor=self.employee_user, event="submit",
        )
        self.assertTrue(NotificationDelivery.objects.filter(
            request_event=event,
            recipient=self.manager_user,
            status=NotificationDelivery.STATUS_QUEUED,
        ).exists())

    def test_initial_entitlement_allocation_queues_generic_owner_email(self):
        entitlement = create_entitlement(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            base_days=Decimal("20.0"),
            actor=self.manager_user,
            reason="opening allocation",
            idempotency_key="notification-opening-allocation",
        )

        delivery = NotificationDelivery.objects.get(
            entitlement_event__entitlement=entitlement,
        )
        self.assertEqual(delivery.recipient_id, self.employee_user.pk)
        self.assertEqual(delivery.source_type, NotificationDelivery.SOURCE_ENTITLEMENT_EVENT)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_QUEUED)

    def test_status_command_reports_aggregates_without_recipient_addresses(self):
        self.queue_employee_delivery()
        output = StringIO()

        call_command("notification_delivery_status", stdout=output)

        self.assertEqual(json.loads(output.getvalue()), {
            "by_safe_error_code": {},
            "by_status": {"queued": 1},
            "total": 1,
        })
        self.assertNotIn(self.employee_user.email, output.getvalue())

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
    )
    def test_in_app_source_queues_idempotent_email_and_provider_acceptance_is_sent(self):
        self.assertEqual(queue_request_event_delivery(self.event), 1)
        self.assertEqual(queue_request_event_delivery(self.event), 0)
        delivery = self.queue_employee_delivery()
        result = deliver_pending_notifications()

        delivery.refresh_from_db()
        self.assertEqual(result["sent"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertIsNotNone(delivery.sent_at)
        self.assertIsNone(delivery.delivered_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("Sensitive reason", mail.outbox[0].body)
        self.assertNotIn("Sensitive decision", mail.outbox[0].body)
        self.assertNotIn("Leave type confidential label", mail.outbox[0].body)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
        EMAIL_HOST_PASSWORD="test-secret-must-not-leak",
    )
    def test_provider_failure_retries_without_storing_credentials_or_raw_error(self):
        delivery = self.queue_employee_delivery()
        start = timezone.now()
        with patch.object(
            DjangoEmailProvider,
            "send",
            side_effect=[
                EmailProviderError("SMTPTransientError", retryable=True),
                None,
            ],
        ) as send:
            first = deliver_pending_notifications(now=start)
            delivery.refresh_from_db()
            self.assertEqual(first["retrying"], 1)
            self.assertEqual(delivery.status, NotificationDelivery.STATUS_QUEUED)
            self.assertEqual(delivery.attempt_count, 1)
            self.assertEqual(delivery.retry_after, start + timedelta(minutes=5))
            self.assertEqual(delivery.last_error_code, "SMTPTransientError")
            self.assertNotIn("test-secret-must-not-leak", str(delivery.__dict__))

            second = deliver_pending_notifications(now=start + timedelta(minutes=5))

        delivery.refresh_from_db()
        self.assertEqual(second["sent"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(delivery.attempt_count, 2)
        self.assertEqual(send.call_count, 2)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
    )
    def test_permanent_provider_rejection_is_failed_without_retry(self):
        delivery = self.queue_employee_delivery()
        with patch.object(
            DjangoEmailProvider,
            "send",
            side_effect=EmailProviderError("SMTPRejected", retryable=False),
        ) as send:
            result = deliver_pending_notifications()

        delivery.refresh_from_db()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_FAILED)
        self.assertEqual(delivery.last_error_code, "SMTPRejected")
        self.assertEqual(delivery.attempt_count, 1)
        send.assert_called_once()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=False,
    )
    def test_missing_provider_configuration_is_unavailable_not_sent(self):
        delivery = self.queue_employee_delivery()
        result = deliver_pending_notifications()

        delivery.refresh_from_db()
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_UNAVAILABLE)
        self.assertEqual(delivery.last_error_code, "EmailProviderNotConfigured")
        self.assertEqual(delivery.attempt_count, 0)
        self.assertEqual(mail.outbox, [])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
        EMAIL_HOST_PASSWORD="fake-provider-secret",
    )
    def test_ambiguous_provider_failure_is_not_retried_or_recorded_raw(self):
        delivery = self.queue_employee_delivery()
        with patch(
            "leave.notification_services.send_mail",
            side_effect=OSError("connection ended with fake-provider-secret"),
        ) as send:
            result = deliver_pending_notifications()

        delivery.refresh_from_db()
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_UNAVAILABLE)
        self.assertEqual(delivery.last_error_code, "DeliveryOutcomeUnknown")
        self.assertNotIn("fake-provider-secret", delivery.last_error_code)
        self.assertEqual(delivery.attempt_count, 1)
        send.assert_called_once()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
    )
    def test_repeated_delivery_job_slot_does_not_send_twice(self):
        delivery = self.queue_employee_delivery()
        slot = timezone.now().replace(second=0, microsecond=0)
        with patch.object(DjangoEmailProvider, "send") as send:
            first = execute_job("notification_delivery", slot)
            replay = execute_job("notification_delivery", slot)

        delivery.refresh_from_db()
        self.assertEqual(first.pk, replay.pk)
        self.assertEqual(first.status, "succeeded")
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(delivery.attempt_count, 1)
        send.assert_called_once()

    def test_delivery_job_runs_in_same_slot_as_manager_reminders(self):
        SystemSetting.objects.create(key="workflow.reminder_after_working_days", value=1)
        delivery = self.queue_employee_delivery()

        executions = run_due_jobs(now=timezone.now())

        job_names = {execution.job_name for execution in executions}
        self.assertIn("manager_reminders", job_names)
        self.assertIn("notification_delivery", job_names)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_UNAVAILABLE)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
    )
    def test_recipient_whose_hr_role_was_revoked_is_not_sent(self):
        hr_user = get_user_model().objects.create_user(
            username="notify-hr", email="hr@example.test",
        )
        assignment = RoleAssignment.objects.create(
            user=hr_user,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=self.company,
        )
        self.event = LeaveRequestEvent.objects.create(
            request=self.request,
            actor=self.employee_user,
            origin="employee",
            event="submit",
            to_status="PENDING",
        )
        queue_request_event_delivery(self.event)
        delivery = NotificationDelivery.objects.get(
            idempotency_key=f"request-event:{self.event.pk}:user:{hr_user.pk}",
        )
        assignment.is_active = False
        assignment.save(update_fields=["is_active"])

        result = deliver_pending_notifications()

        delivery.refresh_from_db()
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_UNAVAILABLE)
        self.assertEqual(delivery.last_error_code, "RecipientNoLongerAuthorized")
        sent_recipients = {address for message in mail.outbox for address in message.to}
        self.assertEqual(
            sent_recipients,
            {self.manager_user.email},
        )
        self.assertNotIn(hr_user.email, sent_recipients)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
    )
    def test_historical_manager_is_not_sent_after_reporting_line_changes(self):
        event = LeaveRequestEvent.objects.create(
            request=self.request,
            actor=self.employee_user,
            origin="employee",
            event="submit",
            to_status="PENDING",
        )
        queue_request_event_delivery(event)
        delivery = NotificationDelivery.objects.get(
            idempotency_key=f"request-event:{event.pk}:user:{self.manager_user.pk}",
        )
        replacement_manager_user = get_user_model().objects.create_user(
            username="notify-new-manager", email="new-manager@example.test",
        )
        replacement_manager = EmployeeProfile.objects.create(
            user=replacement_manager_user,
            company=self.company,
            personnel_code="N-M2",
            start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = replacement_manager
        self.employee.save(update_fields=["manager"])

        result = deliver_pending_notifications()

        delivery.refresh_from_db()
        self.assertEqual(result["unavailable"], 1)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_UNAVAILABLE)
        self.assertEqual(delivery.last_error_code, "RecipientNoLongerAuthorized")
        self.assertEqual(mail.outbox, [])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="leave@example.test",
        ZSH_EMAIL_ENABLED=True,
    )
    def test_confidential_request_never_queues_manager_or_sensitive_content(self):
        confidential_type = LeaveType.objects.create(
            key="notify-confidential", label_fa="CONFIDENTIAL-TYPE",
            counts_against_balance=True, confidential=True, employee_requestable=False,
        )
        confidential_request = LeaveRequest.objects.create(
            employee=self.employee,
            manager_snapshot=self.manager,
            leave_type=confidential_type,
            start_date=dt.date(2026, 11, 3),
            end_date=dt.date(2026, 11, 3),
            working_days="1.0",
            status="PENDING",
            reason="CONFIDENTIAL-REASON",
        )
        confidential_event = LeaveRequestEvent.objects.create(
            request=confidential_request,
            actor=self.manager_user,
            origin="hr",
            event="approve",
            to_status="APPROVED",
        )

        queue_request_event_delivery(confidential_event)
        self.assertFalse(NotificationDelivery.objects.filter(
            idempotency_key=f"request-event:{confidential_event.pk}:user:{self.manager_user.pk}",
        ).exists())
        deliver_pending_notifications()

        self.assertTrue(mail.outbox)
        message_text = "\n".join(message.body for message in mail.outbox)
        self.assertNotIn("CONFIDENTIAL-TYPE", message_text)
        self.assertNotIn("CONFIDENTIAL-REASON", message_text)

    def test_sending_rows_stale_after_worker_crash_are_not_resent_automatically(self):
        delivery = self.queue_employee_delivery()
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            status=NotificationDelivery.STATUS_SENDING,
            updated_at=timezone.now() - timedelta(minutes=16),
        )

        result = deliver_pending_notifications(now=timezone.now())

        delivery.refresh_from_db()
        self.assertEqual(result["sent"], 0)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_UNAVAILABLE)
        self.assertEqual(delivery.last_error_code, "DeliveryOutcomeUnknown")
