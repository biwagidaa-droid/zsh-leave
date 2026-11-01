from django.urls import path

from .calendar_views import (
    calendar_events,
    calendar_holiday_management,
    calendar_holiday_admin,
    calendar_holiday_admin_detail,
    calendar_holidays,
    estimate_working_days,
    holiday_history,
    leave_policies,
    policy_history,
    work_patterns,
    work_patterns_history,
)
from .views import convert_calendar_date, health_check, readiness_check

urlpatterns = [
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="ready"),
    path("calendar/convert-date/", convert_calendar_date, name="calendar-date-conversion"),
    path("calendar/events/", calendar_events, name="calendar-events"),
    path("calendar/holidays/", calendar_holidays, name="calendar-holidays"),
    path("calendar/work-patterns/", work_patterns, name="calendar-work-patterns"),
    path("calendar/policies/", leave_policies, name="calendar-policies"),
    path("calendar/holidays/manage/", calendar_holiday_admin, name="calendar-holiday-admin"),
    path("calendar/holidays/manage/<int:holiday_id>/", calendar_holiday_admin_detail,
         name="calendar-holiday-admin-detail"),
    path("calendar/holidays/manage/<int:holiday_id>/history/", holiday_history,
         name="calendar-holiday-history"),
    path("admin/calendar/work-patterns/", work_patterns_history, name="work-pattern-history"),
    path("admin/calendar/policies/", policy_history, name="policy-history"),
    path("holidays/", calendar_holiday_management, name="holidays"),
    path("holidays/<int:holiday_id>/", calendar_holiday_management, name="holiday-detail"),
    path("working-days/estimate", estimate_working_days, name="working-days-estimate"),
]
