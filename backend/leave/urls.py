from django.urls import path

from .views import convert_calendar_date, health_check, readiness_check

urlpatterns = [
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="ready"),
    path("calendar/convert-date/", convert_calendar_date, name="calendar-date-conversion"),
]
