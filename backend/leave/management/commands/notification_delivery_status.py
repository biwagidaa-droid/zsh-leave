import json

from django.core.management.base import BaseCommand
from django.db.models import Count

from leave.models import NotificationDelivery


class Command(BaseCommand):
    help = "Report notification delivery counts without exposing recipient details."

    def handle(self, *args, **options):
        by_status = {
            row["status"]: row["count"]
            for row in NotificationDelivery.objects.values("status")
            .annotate(count=Count("pk"))
            .order_by("status")
        }
        by_error = {
            row["last_error_code"]: row["count"]
            for row in NotificationDelivery.objects.exclude(last_error_code="")
            .values("last_error_code")
            .annotate(count=Count("pk"))
            .order_by("last_error_code")
        }
        self.stdout.write(json.dumps({
            "total": sum(by_status.values()),
            "by_status": by_status,
            "by_safe_error_code": by_error,
        }, ensure_ascii=True, sort_keys=True))
