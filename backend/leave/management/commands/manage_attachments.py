import json

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from leave.attachment_services import (
    purge_attachment,
    set_attachment_legal_hold,
    subtract_calendar_months,
)
from leave.models import LeaveRequestAttachment


class Command(BaseCommand):
    help = "Review attachment retention and perform explicitly approved hold or purge actions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--action", choices=["list-expired", "purge", "hold", "release-hold"],
            default="list-expired",
        )
        parser.add_argument("--attachment-id", type=int)
        parser.add_argument("--actor", help="Active superuser username for an approved action.")
        parser.add_argument("--reason", help="Required audit reason; do not include personal data.")
        parser.add_argument(
            "--approve", action="store_true",
            help="Explicitly approve the requested hold or purge operation.",
        )

    def handle(self, *args, **options):
        action = options["action"]
        if action in {"list-expired"}:
            if options["approve"] or options["actor"] or options["reason"]:
                raise CommandError("Approval, actor, and reason apply only to mutating actions.")
            if action == "list-expired":
                self._list_expired(options["attachment_id"])
            return

        if not options["approve"]:
            raise CommandError("Mutating attachment actions require --approve.")
        if not options["actor"] or not options["reason"] or not options["reason"].strip():
            raise CommandError("Mutating actions require --actor and a non-empty --reason.")
        if len(options["reason"]) > 500:
            raise CommandError("--reason must be 500 characters or fewer.")
        if options["attachment_id"] is None:
            raise CommandError("Mutating actions require --attachment-id.")

        user_model = get_user_model()
        try:
            actor = user_model.objects.get(
                username=options["actor"], is_active=True, is_superuser=True,
            )
        except user_model.DoesNotExist as exc:
            raise CommandError("--actor must identify an active superuser.") from exc

        try:
            if action == "hold":
                set_attachment_legal_hold(
                    options["attachment_id"], actor=actor,
                    reason=options["reason"].strip(), enabled=True,
                )
            elif action == "release-hold":
                set_attachment_legal_hold(
                    options["attachment_id"], actor=actor,
                    reason=options["reason"].strip(), enabled=False,
                )
            else:
                purge_attachment(
                    options["attachment_id"], actor=actor,
                    reason=options["reason"].strip(),
                )
        except (LeaveRequestAttachment.DoesNotExist, ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Attachment {options['attachment_id']}: {action} completed.")

    def _list_expired(self, attachment_id):
        cutoff = subtract_calendar_months(
            timezone.now(),
            settings.ZSH_ATTACHMENT_RETENTION_MONTHS,
        )
        rows = LeaveRequestAttachment.objects.filter(
            created_at__lte=cutoff,
            legal_hold=False,
            deletion_status__in=[
                LeaveRequestAttachment.DELETION_ACTIVE,
                LeaveRequestAttachment.DELETION_PENDING,
            ],
        ).order_by("created_at", "pk")
        if attachment_id is not None:
            rows = rows.filter(pk=attachment_id)
        self.stdout.write(json.dumps({
            "retentionMonths": settings.ZSH_ATTACHMENT_RETENTION_MONTHS,
            "eligibleAttachmentIds": list(rows.values_list("pk", flat=True)),
        }))
