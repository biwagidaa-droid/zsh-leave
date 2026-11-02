import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from leave.models import (
    AuditEvent,
    Company,
    Department,
    EmployeeProfile,
    OrganizationSite,
    RoleAssignment,
)


class OrganizationSiteApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.company = Company.objects.create(code="SITE-A", name="Company A")
        self.other_company = Company.objects.create(code="SITE-B", name="Company B")
        self.department = Department.objects.create(
            company=self.company, code="OPS", name="Operations",
        )
        self.other_department = Department.objects.create(
            company=self.company, code="FIN", name="Finance",
        )
        self.site = OrganizationSite.objects.create(
            company=self.company, code="NORTH", name="North",
        )
        self.other_site = OrganizationSite.objects.create(
            company=self.company, code="SOUTH", name="South",
        )
        self.foreign_site = OrganizationSite.objects.create(
            company=self.other_company, code="FOREIGN", name="Foreign",
        )
        self.company_employee = self.make_employee(
            "site-employee-a", "A-1", company=self.company, site=self.site,
            department=self.department,
        )
        self.other_site_employee = self.make_employee(
            "site-employee-b", "A-2", company=self.company, site=self.other_site,
            department=self.other_department,
        )
        self.foreign_employee = self.make_employee(
            "site-employee-foreign", "B-1", company=self.other_company,
            site=self.foreign_site,
        )

        self.company_hr = user_model.objects.create_user(username="site-company-hr")
        self.department_hr = user_model.objects.create_user(username="site-department-hr")
        self.site_hr = user_model.objects.create_user(username="site-site-hr")
        self.admin = user_model.objects.create_user(username="site-admin")
        self.assign(
            self.company_hr, RoleAssignment.SCOPE_COMPANY, company=self.company,
        )
        self.assign(
            self.department_hr, RoleAssignment.SCOPE_DEPARTMENT, company=self.company,
            department=self.department,
        )
        self.assign(
            self.site_hr, RoleAssignment.SCOPE_SITE, company=self.company, site=self.site,
        )
        self.assign(self.admin, RoleAssignment.SCOPE_GLOBAL)

        self.company_client = self.client_for(self.company_hr)
        self.department_client = self.client_for(self.department_hr)
        self.site_client = self.client_for(self.site_hr)
        self.admin_client = self.client_for(self.admin)

    @staticmethod
    def client_for(user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    @staticmethod
    def assign(user, scope, company=None, site=None, department=None):
        return RoleAssignment.objects.create(
            user=user,
            role=RoleAssignment.ROLE_HR if scope != RoleAssignment.SCOPE_GLOBAL
            else RoleAssignment.ROLE_ADMIN,
            scope=scope,
            company=company,
            site=site,
            department=department,
        )

    @staticmethod
    def make_employee(username, code, *, company, site=None, department=None, manager=None):
        user = get_user_model().objects.create_user(username=username)
        return EmployeeProfile.objects.create(
            user=user,
            company=company,
            site=site,
            department=department,
            manager=manager,
            personnel_code=code,
            start_date=dt.date(2020, 1, 1),
        )

    def employee_payload(self, employee, **updates):
        payload = {
            "displayName": employee.user.username,
            "personnelCode": employee.personnel_code,
            "companyId": employee.company_id,
            "departmentId": employee.department_id,
        }
        payload.update(updates)
        return payload

    def test_company_hr_site_crud_is_company_scoped_and_admin_is_global(self):
        company_sites = self.company_client.get("/api/v1/sites/")
        self.assertEqual(company_sites.status_code, 200)
        self.assertEqual(
            {item["id"] for item in company_sites.json()},
            {self.site.pk, self.other_site.pk},
        )
        self.assertEqual(
            self.company_client.get(f"/api/v1/sites/{self.site.pk}/").status_code, 200,
        )
        self.assertEqual(
            self.company_client.get(f"/api/v1/sites/{self.foreign_site.pk}/").status_code, 404,
        )

        created = self.company_client.post(
            "/api/v1/sites/",
            {"companyId": self.company.pk, "code": "EAST", "name": "East"},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.content)
        created_site_id = created.json()["id"]
        updated = self.company_client.patch(
            f"/api/v1/sites/{created_site_id}/",
            {"companyId": self.company.pk, "code": "EAST-2", "name": "East II"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["name"], "East II")

        foreign_create = self.company_client.post(
            "/api/v1/sites/",
            {"companyId": self.other_company.pk, "code": "NOPE", "name": "No access"},
            format="json",
        )
        self.assertEqual(foreign_create.status_code, 403)
        foreign_move = self.company_client.patch(
            f"/api/v1/sites/{self.site.pk}/",
            {"companyId": self.other_company.pk, "code": "NORTH", "name": "North"},
            format="json",
        )
        self.assertEqual(foreign_move.status_code, 403)

        admin_sites = self.admin_client.get("/api/v1/sites/")
        self.assertEqual(admin_sites.status_code, 200)
        self.assertIn(self.foreign_site.pk, {item["id"] for item in admin_sites.json()})
        admin_employee_rows = self.admin_client.get("/api/v1/employees/").json()
        self.assertEqual(
            {row["id"] for row in admin_employee_rows},
            {self.company_employee.pk, self.other_site_employee.pk, self.foreign_employee.pk},
        )
        self.assertEqual(
            self.admin_client.get(
                f"/api/v1/employees/{self.foreign_employee.pk}/",
            ).status_code,
            200,
        )
        admin_create = self.admin_client.post(
            "/api/v1/sites/",
            {"companyId": self.other_company.pk, "code": "WEST", "name": "West"},
            format="json",
        )
        self.assertEqual(admin_create.status_code, 201, admin_create.content)
        admin_update = self.admin_client.patch(
            f"/api/v1/sites/{self.site.pk}/",
            {"companyId": self.company.pk, "code": self.site.code, "name": "Renamed"},
            format="json",
        )
        self.assertEqual(admin_update.status_code, 200, admin_update.content)

    def test_department_and_site_scopes_limit_employee_and_site_access(self):
        department_rows = self.department_client.get("/api/v1/employees/").json()
        self.assertEqual({row["id"] for row in department_rows}, {self.company_employee.pk})
        department_sites = self.department_client.get("/api/v1/sites/").json()
        self.assertEqual({row["id"] for row in department_sites}, {self.site.pk})
        self.assertEqual(
            self.department_client.get(f"/api/v1/employees/{self.other_site_employee.pk}/").status_code,
            404,
        )

        site_rows = self.site_client.get("/api/v1/employees/").json()
        self.assertEqual({row["id"] for row in site_rows}, {self.company_employee.pk})
        self.assertEqual(
            {row["id"] for row in self.site_client.get("/api/v1/sites/").json()},
            {self.site.pk},
        )
        self.assertEqual(
            self.site_client.get(f"/api/v1/sites/{self.other_site.pk}/").status_code, 404,
        )
        self.assertEqual(
            self.site_client.get(f"/api/v1/employees/{self.other_site_employee.pk}/").status_code,
            404,
        )

        for client, target_site in (
            (self.department_client, self.site),
            (self.site_client, self.site),
        ):
            response = client.patch(
                f"/api/v1/sites/{target_site.pk}/",
                {"companyId": self.company.pk, "code": target_site.code, "name": "Changed"},
                format="json",
            )
            self.assertEqual(response.status_code, 403)

    def test_only_admin_or_company_hr_can_mutate_sites(self):
        employee_user = self.company_employee.user
        employee_client = self.client_for(employee_user)
        manager = self.make_employee(
            "site-manager", "A-M", company=self.company, site=self.site,
            department=self.department,
        )
        report = self.make_employee(
            "site-report", "A-R", company=self.company, site=self.site,
            department=self.department, manager=manager,
        )
        manager_client = self.client_for(manager.user)

        for username, client in (
            ("site HR", self.site_client),
            ("department HR", self.department_client),
            ("employee", employee_client),
            ("manager", manager_client),
        ):
            with self.subTest(user=username):
                response = client.patch(
                    f"/api/v1/sites/{self.site.pk}/",
                    {"companyId": self.company.pk, "code": self.site.code, "name": "Changed"},
                    format="json",
                )
                self.assertEqual(response.status_code, 403)
        self.assertTrue(EmployeeProfile.objects.filter(pk=report.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(
            entity="OrganizationSite", action="organization_site.update",
        ).exists())

    def test_employee_site_read_write_and_cross_company_rejection(self):
        read_response = self.company_client.get(
            f"/api/v1/employees/{self.company_employee.pk}/",
        )
        self.assertEqual(read_response.status_code, 200)
        self.assertEqual(read_response.json()["siteId"], self.site.pk)
        self.assertEqual(read_response.json()["siteName"], self.site.name)

        changed = self.company_client.patch(
            f"/api/v1/employees/{self.company_employee.pk}/",
            self.employee_payload(self.company_employee, siteId=self.other_site.pk),
            format="json",
        )
        self.assertEqual(changed.status_code, 200, changed.content)
        self.assertEqual(changed.json()["siteId"], self.other_site.pk)

        rejected = self.company_client.patch(
            f"/api/v1/employees/{self.company_employee.pk}/",
            self.employee_payload(self.company_employee, siteId=self.foreign_site.pk),
            format="json",
        )
        self.assertEqual(rejected.status_code, 400)
        self.company_employee.refresh_from_db()
        self.assertEqual(self.company_employee.site_id, self.other_site.pk)

        site_hr_move = self.site_client.patch(
            f"/api/v1/employees/{self.company_employee.pk}/",
            self.employee_payload(self.company_employee, siteId=self.other_site.pk),
            format="json",
        )
        self.assertEqual(site_hr_move.status_code, 404)

    def test_archived_site_preserves_existing_assignment_and_rejects_new_assignment(self):
        archived = self.company_client.patch(
            f"/api/v1/sites/{self.site.pk}/",
            {
                "companyId": self.company.pk, "code": self.site.code, "name": self.site.name,
                "isActive": False,
            },
            format="json",
        )
        self.assertEqual(archived.status_code, 200, archived.content)
        self.assertFalse(archived.json()["isActive"])

        unchanged = self.company_client.patch(
            f"/api/v1/employees/{self.company_employee.pk}/",
            self.employee_payload(self.company_employee),
            format="json",
        )
        self.assertEqual(unchanged.status_code, 200, unchanged.content)
        self.assertEqual(unchanged.json()["siteId"], self.site.pk)

        moved_to_archived = self.company_client.patch(
            f"/api/v1/employees/{self.other_site_employee.pk}/",
            self.employee_payload(self.other_site_employee, siteId=self.site.pk),
            format="json",
        )
        self.assertEqual(moved_to_archived.status_code, 400)

    def test_delete_is_protected_by_references_and_unused_sites_can_be_deleted(self):
        protected = self.company_client.delete(f"/api/v1/sites/{self.site.pk}/")
        self.assertEqual(protected.status_code, 409)
        self.assertTrue(OrganizationSite.objects.filter(pk=self.site.pk).exists())

        unused = OrganizationSite.objects.create(
            company=self.company, code="UNUSED", name="Unused",
        )
        deleted = self.company_client.delete(f"/api/v1/sites/{unused.pk}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(OrganizationSite.objects.filter(pk=unused.pk).exists())
        self.assertTrue(AuditEvent.objects.filter(
            entity="OrganizationSite", entity_id=str(unused.pk),
            action="organization_site.delete",
        ).exists())

    def test_employee_and_manager_can_read_only_their_visible_site_references(self):
        employee_client = self.client_for(self.company_employee.user)
        employee_sites = employee_client.get("/api/v1/sites/").json()
        self.assertEqual({row["id"] for row in employee_sites}, {self.site.pk})
        self.assertEqual(
            employee_client.get(f"/api/v1/sites/{self.other_site.pk}/").status_code, 404,
        )

        manager = self.make_employee(
            "site-read-manager", "M-1", company=self.company, site=self.site,
            department=self.department,
        )
        self.make_employee(
            "site-read-report", "M-2", company=self.company, site=self.other_site,
            department=self.department, manager=manager,
        )
        manager_client = self.client_for(manager.user)
        manager_sites = manager_client.get("/api/v1/sites/").json()
        self.assertEqual(
            {row["id"] for row in manager_sites}, {self.site.pk, self.other_site.pk},
        )
        denied = manager_client.patch(
            f"/api/v1/sites/{self.site.pk}/",
            {"companyId": self.company.pk, "code": self.site.code, "name": "Changed"},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)
