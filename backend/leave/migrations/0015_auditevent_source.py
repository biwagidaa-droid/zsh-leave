from django.db import migrations, models


def restore_audit_event_guard(apps, schema_editor):
    connection = schema_editor.connection
    table = "leave_auditevent"
    if connection.vendor == "postgresql":
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
        schema_editor.execute(f"""
            CREATE TRIGGER {table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION leave_reject_append_only_mutation()
        """)
    elif connection.vendor == "sqlite":
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_no_update")
        schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_no_delete")
        schema_editor.execute(f"""
            CREATE TRIGGER {table}_no_update
            BEFORE UPDATE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only; UPDATE is prohibited');
            END
        """)
        schema_editor.execute(f"""
            CREATE TRIGGER {table}_no_delete
            BEFORE DELETE ON {table}
            BEGIN
                SELECT RAISE(ABORT, '{table} is append-only; DELETE is prohibited');
            END
        """)


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0014_append_only_history_guards"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="source",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.RunPython(restore_audit_event_guard, migrations.RunPython.noop),
    ]
