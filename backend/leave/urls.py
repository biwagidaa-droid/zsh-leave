from django.urls import path

from .views import health_check, readiness_check

urlpatterns = [
    path("health/", health_check, name="health"),
    path("ready/", readiness_check, name="ready"),
]
