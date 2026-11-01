from __future__ import annotations

from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny


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
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        database_ok = True
    except Exception as exc:  # pragma: no cover - defensive check for infra availability.
        database_ok = False
        checks.append({"name": "database", "ok": False, "message": "database unavailable"})
    else:
        checks.append({"name": "database", "ok": True, "message": "database reachable"})

    overall = "ready" if database_ok else "unavailable"
    status_code = 200 if database_ok else 503
    return JsonResponse({
        "status": overall,
        "checks": checks,
        "timestamp": timezone.now().isoformat(),
    }, status=status_code)
