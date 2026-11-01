import datetime as dt

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from leave.employment_services import (
    employees_employed_on,
    employment_filter,
    is_employed_on,
    is_employed_throughout,
    organization_localdate,
)
from leave.models import Company, EmployeeProfile


class EmploymentServiceTests(TestCase):
    def setUp(self):
        self.today = organization_localdate()
        self.company = Company.objects.create(code="EMPLOYMENT", name="Employment test")

    def employee(self, personnel_code, *, start_date=None, end_date=None, **kwargs):
        return EmployeeProfile.objects.create(
            user=get_user_model().objects.create_user(username=personnel_code),
            company=self.company,
            personnel_code=personnel_code,
            start_date=start_date or self.today,
            end_date=end_date,
            **kwargs,
        )

    def test_inclusive_employment_boundaries_and_open_ended_employment(self):
        no_end = self.employee("OPEN-ENDED", start_date=self.today - dt.timedelta(days=1))
        future_start = self.employee(
            "FUTURE-START", start_date=self.today + dt.timedelta(days=1),
        )
        starts_today = self.employee("STARTS-TODAY")
        past_start = self.employee("PAST-START", start_date=self.today - dt.timedelta(days=1))
        future_end = self.employee(
            "FUTURE-END", start_date=self.today - dt.timedelta(days=10),
            end_date=self.today + dt.timedelta(days=1),
        )
        ends_today = self.employee(
            "ENDS-TODAY", start_date=self.today - dt.timedelta(days=10),
            end_date=self.today,
        )
        past_end = self.employee(
            "PAST-END", start_date=self.today - dt.timedelta(days=10),
            end_date=self.today - dt.timedelta(days=1),
        )

        self.assertTrue(is_employed_on(no_end, self.today))
        self.assertFalse(is_employed_on(future_start, self.today))
        self.assertTrue(is_employed_on(future_start, future_start.start_date))
        self.assertTrue(is_employed_on(starts_today, self.today))
        self.assertTrue(is_employed_on(past_start, self.today))
        self.assertTrue(is_employed_on(future_end, self.today))
        self.assertTrue(is_employed_on(ends_today, self.today))
        self.assertFalse(is_employed_on(past_end, self.today))

    def test_current_suspension_and_offboarding_are_ineligible(self):
        suspended = self.employee(
            "SUSPENDED", account_status=EmployeeProfile.ACCOUNT_SUSPENDED,
        )
        offboarded = self.employee(
            "OFFBOARDED", account_status=EmployeeProfile.ACCOUNT_OFFBOARDED,
        )

        self.assertFalse(is_employed_on(suspended, self.today))
        self.assertFalse(is_employed_on(offboarded, self.today))

    def test_audited_status_history_preserves_prior_historical_eligibility(self):
        suspended = self.employee(
            "AUDITED-SUSPENSION",
            start_date=self.today - dt.timedelta(days=10),
            account_status=EmployeeProfile.ACCOUNT_SUSPENDED,
        )
        before_suspension = self.today - dt.timedelta(days=2)
        suspension_date = self.today - dt.timedelta(days=1)
        history = [(suspension_date, EmployeeProfile.ACCOUNT_SUSPENDED)]

        self.assertTrue(is_employed_on(suspended, before_suspension, status_history=history))
        self.assertFalse(is_employed_on(suspended, suspension_date, status_history=history))

    def test_period_eligibility_handles_full_and_partial_employment(self):
        period_start = self.today - dt.timedelta(days=5)
        period_end = self.today + dt.timedelta(days=5)
        full_period = self.employee(
            "FULL-PERIOD", start_date=period_start - dt.timedelta(days=1),
            end_date=period_end + dt.timedelta(days=1),
        )
        starts_mid_period = self.employee(
            "STARTS-MID", start_date=self.today,
        )
        ends_mid_period = self.employee(
            "ENDS-MID", start_date=period_start,
            end_date=self.today,
        )

        self.assertTrue(is_employed_throughout(full_period, period_start, period_end))
        self.assertFalse(is_employed_throughout(starts_mid_period, period_start, period_end))
        self.assertFalse(is_employed_throughout(ends_mid_period, period_start, period_end))

    def test_queryset_filter_matches_current_point_in_time_predicate(self):
        active = self.employee("QUERY-ACTIVE", start_date=self.today - dt.timedelta(days=1))
        future = self.employee(
            "QUERY-FUTURE", start_date=self.today + dt.timedelta(days=1),
        )
        expired = self.employee(
            "QUERY-EXPIRED", start_date=self.today - dt.timedelta(days=2),
            end_date=self.today - dt.timedelta(days=1),
        )
        suspended = self.employee(
            "QUERY-SUSPENDED", account_status=EmployeeProfile.ACCOUNT_SUSPENDED,
        )

        ids = set(employees_employed_on(EmployeeProfile.objects.all(), self.today).values_list(
            "pk", flat=True,
        ))
        self.assertEqual(ids, {active.pk})
        self.assertEqual(
            set(EmployeeProfile.objects.filter(employment_filter(self.today)).values_list(
                "pk", flat=True,
            )),
            ids,
        )
        self.assertFalse(is_employed_on(future, self.today))
        self.assertFalse(is_employed_on(expired, self.today))
        self.assertFalse(is_employed_on(suspended, self.today))

    @override_settings(TIME_ZONE="Asia/Tehran")
    def test_configured_timezone_handles_midnight_and_year_boundary(self):
        utc_instant = dt.datetime(2026, 12, 31, 20, 30, tzinfo=dt.timezone.utc)

        self.assertEqual(organization_localdate(utc_instant), dt.date(2027, 1, 1))
