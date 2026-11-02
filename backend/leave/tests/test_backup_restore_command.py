import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path

from django.db import connection
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings


class VerifyBackupCommandTests(TestCase):
    def test_inventory_compares_restored_counts_and_files(self):
        with tempfile.TemporaryDirectory() as attachment_root:
            storage_root = Path(attachment_root) / "attachments"
            storage_root.mkdir()
            stored_file = storage_root / "leave-attachments" / "request-1" / "fixture.pdf"
            stored_file.parent.mkdir(parents=True)
            stored_file.write_bytes(b"attachment fixture")
            with override_settings(ZSH_ATTACHMENT_ROOT=storage_root):
                output = StringIO()
                call_command("verify_backup", stdout=output)
                inventory = json.loads(output.getvalue())

                self.assertEqual(inventory["database_vendor"], connection.vendor)
                self.assertEqual(inventory["errors"], [])
                self.assertIn("leave.auditevent", inventory["record_counts"])
                self.assertEqual(inventory["attachments"]["file_count"], 1)
                self.assertEqual(inventory["attachments"]["files"][0]["size"], 18)
                self.assertEqual(
                    inventory["attachments"]["files"][0]["sha256"],
                    hashlib.sha256(b"attachment fixture").hexdigest(),
                )

                manifest_path = Path(attachment_root) / "inventory.json"
                manifest_path.write_text(json.dumps(inventory), encoding="utf-8")
                compared_output = StringIO()
                call_command(
                    "verify_backup",
                    "--compare",
                    str(manifest_path),
                    stdout=compared_output,
                )
                self.assertEqual(json.loads(compared_output.getvalue())["errors"], [])

                stored_file.write_bytes(b"modified attachment")
                with self.assertRaises(CommandError):
                    call_command(
                        "verify_backup",
                        "--compare",
                        str(manifest_path),
                        stdout=StringIO(),
                    )

                stored_file.write_bytes(b"attachment fixture")
                inventory["record_counts"]["auth.user"] += 1
                manifest_path.write_text(json.dumps(inventory), encoding="utf-8")
                with self.assertRaises(CommandError):
                    call_command(
                        "verify_backup",
                        "--compare",
                        str(manifest_path),
                        stdout=StringIO(),
                    )
