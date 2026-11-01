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
from .authentication import change_password, current_user, login, logout
from .views import convert_calendar_date, health_check, readiness_check
from .role_assignment_views import role_assignment_detail, role_assignments
from .workflow_views import (
    leave_request_action,
    leave_request_amend,
    leave_request_comments,
    leave_request_detail,
    leave_request_events,
    leave_requests,
)

urlpatterns = [
    path("auth/login", login, name="auth-login"),
    path("auth/logout", logout, name="auth-logout"),
    path("auth/me", current_user, name="auth-me"),
    path("auth/password", change_password, name="auth-password"),
    path("admin/role-assignments/", role_assignments, name="role-assignments"),
    path("admin/role-assignments/<int:assignment_id>/", role_assignment_detail,
         name="role-assignment-detail"),
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
    path("leave-requests/", leave_requests, name="leave-requests"),
    path("leave-requests/<int:request_id>/", leave_request_detail, name="leave-request-detail"),
    path("leave-requests/<int:request_id>/amend", leave_request_amend,
         name="leave-request-amend"),
    path("leave-requests/<int:request_id>/<str:action>", leave_request_action,
         name="leave-request-action"),
    path("leave-requests/<int:request_id>/comments/", leave_request_comments,
         name="leave-request-comments"),
    path("leave-requests/<int:request_id>/events/", leave_request_events,
         name="leave-request-events"),
]
