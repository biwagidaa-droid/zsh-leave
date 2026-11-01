from django.db import migrations


def install_projection_guard(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute("""
            CREATE OR REPLACE FUNCTION leave_entitlement_projection_guard()
            RETURNS trigger AS $$
            DECLARE
                journal_base numeric;
                journal_carry numeric;
                journal_adjustment numeric;
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    IF NEW.base_days <> 0 OR NEW.carry_over_days <> 0
                       OR NEW.manual_adjustment <> 0 THEN
                        RAISE EXCEPTION 'LeaveEntitlement allocation requires ledger entries';
                    END IF;
                    RETURN NEW;
                END IF;

                SELECT COALESCE(SUM(base_delta), 0),
                       COALESCE(SUM(carry_over_delta), 0),
                       COALESCE(SUM(manual_adjustment_delta), 0)
                  INTO journal_base, journal_carry, journal_adjustment
                  FROM leave_entitlementevent
                 WHERE entitlement_id = NEW.id;

                IF NEW.base_days IS DISTINCT FROM journal_base
                   OR NEW.carry_over_days IS DISTINCT FROM journal_carry
                   OR NEW.manual_adjustment IS DISTINCT FROM journal_adjustment THEN
                    RAISE EXCEPTION 'LeaveEntitlement allocation does not match ledger';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_projection_insert_guard
            BEFORE INSERT ON leave_leaveentitlement
            FOR EACH ROW EXECUTE FUNCTION leave_entitlement_projection_guard()
        """)
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_projection_update_guard
            BEFORE UPDATE OF base_days, carry_over_days, manual_adjustment
            ON leave_leaveentitlement
            FOR EACH ROW EXECUTE FUNCTION leave_entitlement_projection_guard()
        """)
    elif connection.vendor == "sqlite":
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_projection_insert_guard
            BEFORE INSERT ON leave_leaveentitlement
            WHEN NEW.base_days != 0 OR NEW.carry_over_days != 0
                 OR NEW.manual_adjustment != 0
            BEGIN
                SELECT RAISE(ABORT, 'LeaveEntitlement allocation requires ledger entries');
            END
        """)
        schema_editor.execute("""
            CREATE TRIGGER leave_entitlement_projection_update_guard
            BEFORE UPDATE OF base_days, carry_over_days, manual_adjustment
            ON leave_leaveentitlement
            WHEN NEW.base_days != COALESCE(
                     (SELECT SUM(base_delta) FROM leave_entitlementevent
                       WHERE entitlement_id = OLD.id), 0)
              OR NEW.carry_over_days != COALESCE(
                     (SELECT SUM(carry_over_delta) FROM leave_entitlementevent
                       WHERE entitlement_id = OLD.id), 0)
              OR NEW.manual_adjustment != COALESCE(
                     (SELECT SUM(manual_adjustment_delta) FROM leave_entitlementevent
                       WHERE entitlement_id = OLD.id), 0)
            BEGIN
                SELECT RAISE(ABORT, 'LeaveEntitlement allocation does not match ledger');
            END
        """)


def remove_projection_guard(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS leave_entitlement_projection_insert_guard "
            "ON leave_leaveentitlement"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS leave_entitlement_projection_update_guard "
            "ON leave_leaveentitlement"
        )
        schema_editor.execute("DROP FUNCTION IF EXISTS leave_entitlement_projection_guard()")
    elif connection.vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS leave_entitlement_projection_insert_guard"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS leave_entitlement_projection_update_guard"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0008_entitlement_event_immutability"),
    ]

    operations = [
        migrations.RunPython(install_projection_guard, remove_projection_guard),
    ]
