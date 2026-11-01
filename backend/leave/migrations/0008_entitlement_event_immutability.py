from django.db import migrations


def install_immutable_triggers(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION leave_entitlement_event_immutable()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'EntitlementEvent rows are append-only';
            END;
            $$ LANGUAGE plpgsql
        """)
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_event_immutable_trigger
            BEFORE UPDATE OR DELETE ON leave_entitlementevent
            FOR EACH ROW EXECUTE FUNCTION leave_entitlement_event_immutable()
        """)
    elif connection.vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_event_no_update
            BEFORE UPDATE ON leave_entitlementevent
            BEGIN
                SELECT RAISE(ABORT, 'EntitlementEvent rows are append-only');
            END
        """)
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_event_no_delete
            BEFORE DELETE ON leave_entitlementevent
            BEGIN
                SELECT RAISE(ABORT, 'EntitlementEvent rows are append-only');
            END
        """)


def remove_immutable_triggers(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS leave_entitlement_event_immutable_trigger "
            "ON leave_entitlementevent"
        )
        schema_editor.execute("DROP FUNCTION IF EXISTS leave_entitlement_event_immutable()")
    elif connection.vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS leave_entitlement_event_no_update")
        schema_editor.execute("DROP TRIGGER IF EXISTS leave_entitlement_event_no_delete")


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0007_entitlement_ledger_backfill"),
    ]

    operations = [
        migrations.RunPython(install_immutable_triggers, remove_immutable_triggers),
    ]
