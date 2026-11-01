import datetime as dt
from io import StringIO
import threading
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from leave.hierarchy_services import hierarchy_issues
from leave.models import Company, Department, EmployeeProfile


class OrganizationalHierarchyIntegrityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(code="HIER", name="Hierarchy")
        self.other_company = Company.objects.create(code="HIER-OTHER", name="Other")
        self.root = Department.objects.create(
            company=self.company, code="ROOT", name="Root",
        )

    def make_employee(self, code, **kwargs):
        user = get_user_model().objects.create_user(username=f"hier-{code}")
        start_date = kwargs.pop("start_date", dt.date(2020, 1, 1))
        return EmployeeProfile.objects.create(
            user=user,
            company=self.company,
            personnel_code=code,
            start_date=start_date,
            **kwargs,
        )

    def test_department_rejects_self_parent_and_cross_company_parent(self):
        department = Department.objects.create(
            company=self.company, code="SELF", name="Self",
        )
        department.parent = department
        with self.assertRaises(ValidationError):
            department.save()
        department.refresh_from_db()
        self.assertIsNone(department.parent_id)

        foreign_parent = Department.objects.create(
            company=self.other_company, code="FOREIGN", name="Foreign",
        )
        department.parent = foreign_parent
        with self.assertRaises(ValidationError):
            department.save()

    def test_database_constraint_rejects_department_self_parent(self):
        department = Department.objects.create(
            company=self.company, code="DB-SELF", name="Database self",
        )
        table = connection.ops.quote_name(Department._meta.db_table)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE {table} SET parent_id = %s WHERE id = %s",
                        [department.pk, department.pk],
                    )

    def test_department_rejects_two_node_and_multi_level_cycles(self):
        first = Department.objects.create(company=self.company, code="D1", name="One")
        second = Department.objects.create(
            company=self.company, code="D2", name="Two", parent=first,
        )
        first.parent = second
        with self.assertRaises(ValidationError):
            first.save()
        first.refresh_from_db()
        self.assertIsNone(first.parent_id)

        third = Department.objects.create(
            company=self.company, code="D3", name="Three", parent=second,
        )
        first.parent = third
        with self.assertRaises(ValidationError):
            first.save()

    def test_valid_nested_departments_and_company_reassignment_rules(self):
        child = Department.objects.create(
            company=self.company, code="CHILD", name="Child", parent=self.root,
        )
        self.assertEqual(child.parent_id, self.root.pk)

        descendant = Department.objects.create(
            company=self.company, code="GRAND", name="Grandchild", parent=child,
        )
        child.company = self.other_company
        with self.assertRaises(ValidationError):
            child.save()
        descendant.refresh_from_db()
        self.assertEqual(descendant.company_id, self.company.pk)

    def test_manager_rejects_self_reference_two_and_three_person_cycles(self):
        first = self.make_employee("M1")
        second = self.make_employee("M2")
        third = self.make_employee("M3")

        first.manager = first
        with self.assertRaises(ValidationError):
            first.save()

        first.manager = second
        first.save(update_fields=["manager"])
        second.manager = first
        with self.assertRaises(ValidationError):
            second.save()
        second.refresh_from_db()
        self.assertIsNone(second.manager_id)

        second.manager = third
        second.save(update_fields=["manager"])
        third.manager = first
        with self.assertRaises(ValidationError):
            third.save()

    def test_valid_manager_hierarchy_and_inactive_manager_rejection(self):
        senior = self.make_employee("SENIOR")
        manager = self.make_employee("MANAGER", manager=senior)
        report = self.make_employee("REPORT", manager=manager)
        self.assertEqual(report.manager.manager_id, senior.pk)

        manager.account_status = EmployeeProfile.ACCOUNT_SUSPENDED
        with self.assertRaises(ValidationError):
            manager.save(update_fields=["account_status"])

        inactive = self.make_employee(
            "INACTIVE", account_status=EmployeeProfile.ACCOUNT_SUSPENDED,
        )
        report.manager = inactive
        with self.assertRaises(ValidationError):
            report.save(update_fields=["manager"])

    def test_manager_must_be_currently_employed_and_same_company(self):
        today = timezone.localdate()
        future = self.make_employee("FUTURE", start_date=today + dt.timedelta(days=1))
        report = self.make_employee("DATE-REPORT")
        report.manager = future
        with self.assertRaises(ValidationError):
            report.save(update_fields=["manager"])

        expired = self.make_employee(
            "EXPIRED", end_date=today - dt.timedelta(days=1),
        )
        report.manager = expired
        with self.assertRaises(ValidationError):
            report.save(update_fields=["manager"])

        foreign_user = get_user_model().objects.create_user(username="hier-foreign")
        foreign = EmployeeProfile.objects.create(
            user=foreign_user, company=self.other_company, personnel_code="FOREIGN",
            start_date=dt.date(2020, 1, 1),
        )
        report.manager = foreign
        with self.assertRaises(ValidationError):
            report.save(update_fields=["manager"])

    def test_queryset_bulk_relationship_writes_cannot_bypass_validation(self):
        child = Department.objects.create(
            company=self.company, code="BULK-CHILD", name="Bulk child", parent=self.root,
        )
        self.root.parent = child
        with self.assertRaises(ValidationError):
            Department.objects.bulk_update([self.root], ["parent"])
        with self.assertRaises(ValidationError):
            Department.objects.filter(pk=self.root.pk).update(parent=child)

        manager = self.make_employee("BULK-MANAGER")
        report = self.make_employee("BULK-REPORT")
        report.manager = manager
        report.save(update_fields=["manager"])
        manager.manager = report
        with self.assertRaises(ValidationError):
            EmployeeProfile.objects.bulk_update([manager], ["manager"])
        with self.assertRaises(ValidationError):
            EmployeeProfile.objects.filter(pk=manager.pk).update(manager=report)

    def test_employee_cannot_move_company_while_managing_reports(self):
        manager = self.make_employee("TRANSFER-MANAGER")
        self.make_employee("TRANSFER-REPORT", manager=manager)
        manager.company = self.other_company
        with self.assertRaises(ValidationError):
            manager.save()

    def test_deletion_preserves_parent_and_manager_relationship_integrity(self):
        child_department = Department.objects.create(
            company=self.company, code="DELETE-CHILD", name="Child", parent=self.root,
        )
        with self.assertRaises(ProtectedError):
            self.root.delete()
        self.assertTrue(Department.objects.filter(pk=child_department.pk).exists())

        manager = self.make_employee("DELETE-MANAGER")
        report = self.make_employee("DELETE-REPORT", manager=manager)
        EmployeeProfile.objects.filter(pk=manager.pk).delete()
        report.refresh_from_db()
        self.assertIsNone(report.manager_id)

    def test_hierarchy_diagnostic_is_empty_for_valid_records(self):
        manager = self.make_employee("DIAG-MANAGER")
        self.make_employee("DIAG-REPORT", manager=manager)
        Department.objects.create(
            company=self.company, code="DIAG-CHILD", name="Diagnostic child",
            parent=self.root,
        )
        self.assertEqual(hierarchy_issues(), [])

    def test_diagnostic_defaults_to_dry_run_and_repair_requires_approval(self):
        broken = Department.objects.create(
            company=self.company, code="BROKEN", name="Broken",
        )
        foreign_parent = Department.objects.create(
            company=self.other_company, code="BROKEN-PARENT", name="Foreign parent",
        )
        table = connection.ops.quote_name(Department._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table} SET parent_id = %s WHERE id = %s",
                [foreign_parent.pk, broken.pk],
            )

        output = StringIO()
        call_command("check_org_hierarchy", stdout=output)
        self.assertIn('"dryRun": true', output.getvalue())
        self.assertEqual(Department.objects.get(pk=broken.pk).parent_id, foreign_parent.pk)
        with self.assertRaises(CommandError):
            call_command("check_org_hierarchy", apply=True, stdout=StringIO())

        call_command(
            "check_org_hierarchy", apply=True, approve=True, stdout=StringIO(),
        )
        broken.refresh_from_db()
        self.assertIsNone(broken.parent_id)
        self.assertEqual(hierarchy_issues(), [])


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row-level locking.")
class ConcurrentHierarchyUpdateTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_manager_updates_cannot_create_a_cycle(self):
        company = Company.objects.create(code="CONCURRENT", name="Concurrent")
        users = [
            get_user_model().objects.create_user(username=f"concurrent-{index}")
            for index in range(2)
        ]
        employees = [
            EmployeeProfile.objects.create(
                user=user, company=company, personnel_code=f"C-{index}",
                start_date=dt.date(2020, 1, 1),
            )
            for index, user in enumerate(users)
        ]
        barrier = threading.Barrier(2)
        results = []

        def assign(source_id, manager_id):
            close_old_connections()
            try:
                source = EmployeeProfile.objects.get(pk=source_id)
                source.manager_id = manager_id
                barrier.wait(timeout=5)
                try:
                    source.save(update_fields=["manager"])
                    results.append("saved")
                except ValidationError:
                    results.append("rejected")
            finally:
                close_old_connections()

        workers = [
            threading.Thread(target=assign, args=(employees[0].pk, employees[1].pk)),
            threading.Thread(target=assign, args=(employees[1].pk, employees[0].pk)),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)

        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertCountEqual(results, ["saved", "rejected"])
        self.assertEqual(hierarchy_issues(), [])
