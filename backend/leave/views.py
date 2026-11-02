from __future__ import annotations

import datetime as dt

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .job_services import scheduler_state
from zsh_core import jalali


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return JsonResponse({
        "status": "ok",
        "service": "zsh-leave",
        "timestamp": timezone.now().isoformat(),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def readiness_check(request):
    checks = []
    database_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database_ok = True
    except Exception:  # pragma: no cover - defensive check for infra availability.
        database_ok = False
        checks.append({"name": "database", "ok": False, "message": "database unavailable"})
    else:
        checks.append({"name": "database", "ok": True, "message": "database reachable"})

    scheduler_required = settings.ZSH_JOB_SCHEDULER_REQUIRED or settings.ZSH_JOB_SCHEDULER_ENABLED
    scheduler_ok = True
    if scheduler_required and database_ok:
        state = scheduler_state()
        scheduler_ok = state["status"] == "healthy"
        checks.append({
            "name": "scheduler",
            "ok": scheduler_ok,
            "status": state["status"],
            "message": "scheduler heartbeat current" if scheduler_ok else "scheduler heartbeat unavailable",
        })
    else:
        checks.append({
            "name": "scheduler",
            "ok": True,
            "status": "not_required",
            "message": "scheduler is not required in this environment",
        })

    ready = database_ok and scheduler_ok
    overall = "ready" if ready else "unavailable"
    status_code = 200 if ready else 503
    return JsonResponse({
        "status": overall,
        "checks": checks,
        "timestamp": timezone.now().isoformat(),
    }, status=status_code)


@api_view(["GET"])
@permission_classes([AllowAny])
def convert_calendar_date(request):
    calendar = request.query_params.get("calendar")
    value = request.query_params.get("date")
    if calendar not in {"jalali", "gregorian"}:
        return Response({
            "code": "invalid_calendar",
            "message_fa": "تقویم باید jalali یا gregorian باشد",
        }, status=400)
    if not value:
        return Response({
            "code": "missing_date",
            "message_fa": "تاریخ الزامی است",
        }, status=400)

    try:
        if calendar == "jalali":
            gregorian_date = jalali.parse_jalali(value)
        else:
            gregorian_date = dt.date.fromisoformat(value)
            if gregorian_date.isoformat() != value:
                raise ValueError("تاریخ میلادی باید به قالب YYYY-MM-DD باشد")
        jalali_date = jalali.format_jalali(gregorian_date)
    except ValueError as exc:
        return Response({
            "code": "invalid_date",
            "message_fa": str(exc),
        }, status=400)

    return Response({
        "gregorian": gregorian_date.isoformat(),
        "jalali": jalali_date,
    })
