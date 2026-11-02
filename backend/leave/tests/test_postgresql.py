import datetime as dt
from decimal import Decimal
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.migrations.recorder import MigrationRecorder
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from leave.authorization import authorization_context, hr_operation_employees
from leave.models import (
    AuditEvent,
    Company,
    EmployeeProfile,
    LeaveRequest,
    LeaveType,
    PublicHoliday,
    RoleAssignment,
)


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL.")
class PostgreSQLCompatibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.hr_user = user_model.objects.create_user(username="pg-audit-hr")
        self.employee_user = user_model.objects.create_user(username="pg-audit-employee")
        self.company = Company.objects.create(code="PGAUDIT", name="PostgreSQL audit")
        self.employee = EmployeeProfile.objects.create(
            user=self.employee_user,
            company=self.company,
            personnel_code="PG-AUDIT-1",
            start_date=dt.date(2020, 1, 1),
        )
        RoleAssignment.objects.create(
            user=self.hr_user,
            role=RoleAssignment.ROLE_HR,
            scope=RoleAssignment.SCOPE_COMPANY,
            company=self.company,
        )
        leave_type = LeaveType.objects.create(
            key="pg-audit-annual",
            label_fa="Annual leave",
        )
        self.request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=dt.date(2026, 11, 2),
            end_date=dt.date(2026, 11, 2),
            working_days=Decimal("1"),
            status="PENDING",
        )
        self.request_audit = AuditEvent.objects.create(
            actor=self.hr_user,
            origin="test",
            action="leave.submit",
            entity="LeaveRequest",
            entity_id=str(self.request.pk),
        )

    def test_scoped_audit_query_casts_numeric_subquery_to_text(self):
        client = APIClient()
        client.force_authenticate(self.hr_user)

        with CaptureQueriesContext(connection) as queries:
            response = client.get("/api/v1/audit/events/")

        self.assertEqual(response.status_code, 200, response.content)
        audit_queries = [
            query["sql"] for query in queries.captured_queries
            if f'FROM "{AuditEvent._meta.db_table}"' in query["sql"]
        ]
        self.assertEqual(len(audit_queries), 1)
        self.assertIn("::varchar", audit_queries[0])
        event = next(
            row for row in response.json()
            if row["id"] == self.request_audit.pk
        )
        self.assertEqual(event["entityId"], str(self.request.pk))

    def test_numeric_subquery_without_cast_is_rejected_by_postgresql(self):
        request_ids = LeaveRequest.objects.order_by().values("pk")

        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                list(AuditEvent.objects.filter(
                    entity="LeaveRequest",
                    entity_id__in=request_ids,
                ).values_list("pk", flat=True))

    def test_numeric_and_nonnumeric_entity_ids_remain_text(self):
        export_audit = AuditEvent.objects.create(
            actor=self.hr_user,
            origin="test",
            action="data.exported",
            entity="Export",
            entity_id="leave-requests",
        )

        self.assertEqual(
            AuditEvent.objects.get(pk=self.request_audit.pk).entity_id,
            str(self.request.pk),
        )
        self.assertEqual(
            AuditEvent.objects.get(
                entity="Export",
                entity_id__in=["leave-requests"],
            ).pk,
            export_audit.pk,
        )

    def test_scoped_employee_query_can_be_locked(self):
        employees = hr_operation_employees(authorization_context(self.hr_user))
        with transaction.atomic():
            locked_employee = employees.select_for_update().get(pk=self.employee.pk)

        self.assertEqual(locked_employee.pk, self.employee.pk)

    def test_audit_timestamp_is_timezone_aware_and_uses_timestamptz(self):
        event = AuditEvent.objects.get(pk=self.request_audit.pk)
        self.assertTrue(timezone.is_aware(event.created_at))
        self.assertTrue(AuditEvent.objects.filter(
            pk=event.pk,
            created_at__gte=event.created_at,
            created_at__lte=timezone.now(),
        ).exists())

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() "
                "AND table_name = %s AND column_name = %s",
                [AuditEvent._meta.db_table, "created_at"],
            )
            self.assertEqual(cursor.fetchone()[0], "timestamp with time zone")

    def test_nulls_distinct_false_unique_constraint_is_enforced(self):
        holiday = {
            "scope": "*",
            "jalali_year": None,
            "jalali_month": 1,
            "jalali_day": 1,
            "label": "Annual holiday",
        }
        PublicHoliday.objects.create(**holiday)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PublicHoliday.objects.create(**holiday)

    def test_postgresql_test_database_applied_the_full_migration_chain(self):
        applied = MigrationRecorder(connection).applied_migrations()
        self.assertIn(("leave", "0018_jobeffect_schedulerheartbeat_jobexecution"), applied)
