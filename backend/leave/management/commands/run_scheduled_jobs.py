import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from leave.job_services import record_scheduler_heartbeat, run_due_jobs


class Command(BaseCommand):
    help = "Record scheduler health and execute due background jobs once."

    def add_arguments(self, parser):
        parser.add_argument(
            "--enable-local",
            action="store_true",
            help="Allow a one-shot run when DEBUG=True and the scheduler flag is disabled.",
        )

    def handle(self, *args, **options):
        if not settings.ZSH_JOB_SCHEDULER_ENABLED and not (
            settings.DEBUG and options["enable_local"]
        ):
            raise CommandError(
                "Scheduler is not configured. Set ZSH_JOB_SCHEDULER_ENABLED=1; "
                "--enable-local is available only with DEBUG=True."
            )

        now = timezone.now()
        record_scheduler_heartbeat(now)
        executions = run_due_jobs(now)
        self.stdout.write(json.dumps({
            "scheduler": "enabled",
            "checkedAt": now.isoformat(),
            "executions": [
                {
                    "job": execution.job_name,
                    "scheduledFor": execution.scheduled_for.isoformat(),
                    "status": execution.status,
                    "attemptCount": execution.attempt_count,
                    "correlationId": execution.correlation_id,
                }
                for execution in executions
            ],
        }, ensure_ascii=False))
