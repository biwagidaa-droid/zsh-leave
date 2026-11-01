from django.db import migrations
from django.db.utils import NotSupportedError


APPEND_ONLY_TABLES = (
    "leave_auditevent",
    "leave_calendarholidayhistory",
    "leave_leaverequestcomment",
    "leave_leaverequestevent",
    "leave_leavepolicyversion",
    "leave_publicholidayhistory",
)


def install_append_only_guards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION leave_reject_append_only_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION USING
                    ERRCODE = '55000',
                    MESSAGE = TG_TABLE_NAME ||
                        ' is append-only; UPDATE and DELETE are prohibited';
            END;
            $$ LANGUAGE plpgsql
        """)
        for table in APPEND_ONLY_TABLES:
            schema_editor.execute(f"""
                CREATE TRIGGER {table}_append_only
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION leave_reject_append_only_mutation()
            """)
    elif connection.vendor == "sqlite":
        for table in APPEND_ONLY_TABLES:
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
    else:
        raise NotSupportedError(
            f"Append-only history guards are not implemented for {connection.vendor}."
        )


def remove_append_only_guards(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        for table in APPEND_ONLY_TABLES:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS leave_reject_append_only_mutation()"
        )
    elif connection.vendor == "sqlite":
        for table in APPEND_ONLY_TABLES:
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_no_update")
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {table}_no_delete")
    else:
        raise NotSupportedError(
            f"Append-only history guards are not implemented for {connection.vendor}."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0013_employeeprofile_account_status_and_more"),
    ]

    operations = [
        migrations.RunPython(install_append_only_guards, remove_append_only_guards),
    ]
