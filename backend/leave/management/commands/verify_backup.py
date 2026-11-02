import hashlib
import json
import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.utils import timezone

from leave.entitlement_services import reconcile_entitlements
from leave.models import (
    AuditEvent,
    CalendarHolidayHistory,
    EntitlementEvent,
    LeaveRequestEvent,
)


class Command(BaseCommand):
    help = "Create or compare a read-only integrity inventory for a backup restore."

    def add_arguments(self, parser):
        parser.add_argument(
            "--compare",
            help="Compare against a JSON inventory file, or '-' to read it from stdin.",
        )

    def handle(self, *args, **options):
        errors = []
        migration_loader = MigrationLoader(connection)
        conflicts = migration_loader.detect_conflicts()
        missing_migrations = sorted(
            f"{app_label}:{name}"
            for app_label, name in migration_loader.graph.leaf_nodes()
            if (app_label, name) not in migration_loader.applied_migrations
        )
        if conflicts:
            errors.append(f"Conflicting migration names: {conflicts}")
        if missing_migrations:
            errors.append(f"Unapplied migration leaves: {missing_migrations}")

        try:
            connection.check_constraints()
            foreign_keys = "checked"
        except Exception as exc:
            foreign_keys = "failed"
            errors.append(f"Database constraint check failed: {type(exc).__name__}")

        record_counts = {
            f"{model._meta.app_label}.{model._meta.model_name}": model._default_manager.count()
            for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
        }
        attachment_files = self._attachment_manifest(errors)
        entitlement_results = reconcile_entitlements()
        inconsistent_entitlements = [
            result["entitlement_id"] for result in entitlement_results if not result["ok"]
        ]
        if inconsistent_entitlements:
            errors.append(
                f"Entitlement ledger reconciliation failed for IDs: {inconsistent_entitlements}"
            )

        database_identity = self._database_identity()
        inventory = {
            "created_at": timezone.now().isoformat(),
            "application_version": os.environ.get("ZSH_APP_VERSION", "unknown"),
            "database_identity": database_identity,
            "database_vendor": connection.vendor,
            "migration_heads": sorted(
                f"{app_label}:{name}" for app_label, name in migration_loader.graph.leaf_nodes()
            ),
            "migration_applied_count": len(migration_loader.applied_migrations),
            "record_counts": record_counts,
            "foreign_key_check": foreign_keys,
            "attachments": {
                "file_count": len(attachment_files),
                "files": attachment_files,
            },
            "history_counts": {
                "audit_events": AuditEvent.objects.count(),
                "leave_request_events": LeaveRequestEvent.objects.count(),
                "calendar_holiday_history": CalendarHolidayHistory.objects.count(),
                "entitlement_events": EntitlementEvent.objects.count(),
            },
            "entitlement_reconciliation": {
                "checked": len(entitlement_results),
                "inconsistent_ids": inconsistent_entitlements,
            },
            "errors": errors,
        }

        compare_path = options["compare"]
        if compare_path:
            try:
                if compare_path == "-":
                    expected = json.load(self.stdin)
                else:
                    with Path(compare_path).open(encoding="utf-8") as source:
                        expected = json.load(source)
            except (OSError, json.JSONDecodeError) as exc:
                raise CommandError("Could not read the comparison inventory.") from exc
            self._compare_inventory(expected, inventory, errors)
            inventory["errors"] = errors

        self.stdout.write(json.dumps(inventory, ensure_ascii=True, sort_keys=True))
        if errors:
            raise CommandError("Backup inventory verification failed.")

    def _database_identity(self):
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT current_database(), current_user, current_setting('server_version')"
                )
                name, user, server_version = cursor.fetchone()
        else:
            name = connection.settings_dict.get("NAME", "")
            user = connection.settings_dict.get("USER", "")
            server_version = connection.Database.sqlite_version
        return {
            "name": str(name),
            "user": str(user),
            "host": str(connection.settings_dict.get("HOST", "")),
            "port": str(connection.settings_dict.get("PORT", "")),
            "server_version": str(server_version),
        }

    def _attachment_manifest(self, errors):
        root = Path(settings.ZSH_ATTACHMENT_ROOT).resolve()
        if not root.is_dir():
            errors.append("Attachment storage root is unavailable.")
            return []

        entries = []
        for directory, subdirectories, filenames in os.walk(root, followlinks=False):
            current = Path(directory)
            for child in list(subdirectories):
                child_path = current / child
                if child_path.is_symlink():
                    errors.append(f"Attachment storage contains a symlink: {child_path.relative_to(root)}")
                    subdirectories.remove(child)
            for filename in filenames:
                file_path = current / filename
                relative_path = file_path.relative_to(root).as_posix()
                if file_path.is_symlink() or not file_path.is_file():
                    errors.append(f"Attachment storage contains a non-regular file: {relative_path}")
                    continue
                digest = hashlib.sha256()
                try:
                    with file_path.open("rb") as stored_file:
                        for chunk in iter(lambda: stored_file.read(1024 * 1024), b""):
                            digest.update(chunk)
                    entries.append({
                        "path": relative_path,
                        "size": file_path.stat().st_size,
                        "sha256": digest.hexdigest(),
                    })
                except OSError as exc:
                    errors.append(f"Could not read attachment file {relative_path}: {type(exc).__name__}")

        entries.sort(key=lambda entry: entry["path"])
        for attachment in apps.get_model("leave", "LeaveRequestAttachment").objects.only(
            "pk", "file", "file_size", "deletion_status",
        ).iterator():
            if attachment.deletion_status == "deleted":
                continue
            try:
                if not attachment.file or not attachment.file.storage.exists(attachment.file.name):
                    errors.append(f"Attachment row {attachment.pk} has no stored file.")
                    continue
                actual_size = attachment.file.storage.size(attachment.file.name)
                if actual_size != attachment.file_size:
                    errors.append(f"Attachment row {attachment.pk} has a size mismatch.")
            except OSError as exc:
                errors.append(f"Attachment row {attachment.pk} could not be checked: {type(exc).__name__}")
        return entries

    @staticmethod
    def _compare_inventory(expected, actual, errors):
        fields = (
            "application_version",
            "migration_heads",
            "record_counts",
            "attachments",
            "history_counts",
            "entitlement_reconciliation",
        )
        for field in fields:
            if expected.get(field) != actual.get(field):
                errors.append(f"Restored {field} does not match the backup inventory.")
