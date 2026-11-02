import json

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from leave.hierarchy_services import hierarchy_issues, repair_hierarchy_issues


class Command(BaseCommand):
    help = "Report organizational hierarchy violations; repair requires explicit approval."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply safe edge removals.")
        parser.add_argument(
            "--approve", action="store_true",
            help="Explicitly approve clearing invalid parent, department, or manager links.",
        )

    def handle(self, *args, **options):
        if options["apply"] and not options["approve"]:
            raise CommandError("--apply requires --approve")
        if options["approve"] and not options["apply"]:
            raise CommandError("--approve is meaningful only with --apply")

        before = hierarchy_issues()
        if options["apply"] and before:
            try:
                repaired = repair_hierarchy_issues()
            except ValidationError as exc:
                raise CommandError(f"Safe repair failed without committing changes: {exc}") from exc
            after = hierarchy_issues()
        else:
            repaired = 0
            after = before
        self.stdout.write(json.dumps({
            "dryRun": not options["apply"],
            "found": len(before),
            "repairedEdges": repaired,
            "remaining": after,
        }, ensure_ascii=False, indent=2))
