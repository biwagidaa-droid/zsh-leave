import datetime as dt

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RoleAssignmentDataMigrationTests(TransactionTestCase):
    migrate_from = ("leave", "0003_publicholiday_is_active_publicholiday_updated_at_and_more")
    migrate_to = ("leave", "0004_roleassignment")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_from])
        old_apps = executor.loader.project_state([self.migrate_from]).apps
        User = old_apps.get_model("auth", "User")
        Group = old_apps.get_model("auth", "Group")
        Company = old_apps.get_model("leave", "Company")
        EmployeeProfile = old_apps.get_model("leave", "EmployeeProfile")
        company = Company.objects.create(code="MIGRATE", name="Migration Company")
        hr_user = User.objects.create(
            username="migrated-hr", is_active=True,
        )
        exec_user = User.objects.create(
            username="migrated-exec", is_active=True,
        )
        admin_user = User.objects.create(
            username="migrated-admin", is_active=True, is_superuser=True,
        )
        orphan_user = User.objects.create(
            username="unmapped-hr", is_active=True,
        )
        EmployeeProfile.objects.create(
            user_id=hr_user.pk, company_id=company.pk, personnel_code="M-1",
            start_date=dt.date(2020, 1, 1),
        )
        EmployeeProfile.objects.create(
            user_id=exec_user.pk, company_id=company.pk, personnel_code="M-2",
            start_date=dt.date(2020, 1, 1),
        )
        hr_group = Group.objects.create(name="HR")
        exec_group = Group.objects.create(name="Executive")
        hr_user.groups.add(hr_group)
        orphan_user.groups.add(hr_group)
        exec_user.groups.add(exec_group)

        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        new_apps = executor.loader.project_state([self.migrate_to]).apps
        RoleAssignment = new_apps.get_model("leave", "RoleAssignment")
        AuditEvent = new_apps.get_model("leave", "AuditEvent")
        self.assignments = list(
            RoleAssignment.objects.order_by("role", "user_id").values_list(
                "user__username", "role", "scope", "company_id",
            )
        )
        self.migrated_audit_count = AuditEvent.objects.filter(
            action="role.assignment.migrated",
        ).count()

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_roles_are_mapped_only_with_valid_organization_scope(self):
        self.assertIn(("migrated-admin", "admin", "global", None), self.assignments)
        self.assertIn(("migrated-hr", "hr", "company", 1), self.assignments)
        self.assertIn(("migrated-exec", "exec", "company", 1), self.assignments)
        self.assertNotIn("unmapped-hr", {row[0] for row in self.assignments})
        self.assertEqual(self.migrated_audit_count, 3)
