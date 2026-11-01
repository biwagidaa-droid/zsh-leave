import datetime as dt
from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations

from zsh_core.jalali import from_gregorian


def _snapshot(values):
    return {
        "base_days": str(values["base"]),
        "carry_over_days": str(values["carry"]),
        "manual_adjustment": str(values["adjustment"]),
        "reserved_days": str(values["reserved"]),
        "used_days": str(values["used"]),
    }


def backfill_entitlement_journal(apps, schema_editor):
    Entitlement = apps.get_model("leave", "LeaveEntitlement")
    Event = apps.get_model("leave", "EntitlementEvent")
    Request = apps.get_model("leave", "LeaveRequest")
    db = schema_editor.connection.alias
    states = {}
    entitlement_ids = {}

    for row in Entitlement.objects.using(db).order_by("pk").iterator(chunk_size=500):
        state = {
            "base": row.base_days,
            "carry": row.carry_over_days,
            "adjustment": row.manual_adjustment,
            "reserved": Decimal("0"),
            "used": Decimal("0"),
        }
        states[row.pk] = state
        entitlement_ids[(row.employee_id, row.leave_type_id, row.year)] = row.pk
        Event.objects.using(db).create(
            entitlement_id=row.pk,
            kind="opening",
            before=_snapshot({**state, "base": Decimal("0"), "carry": Decimal("0"),
                              "adjustment": Decimal("0")}),
            after=_snapshot(state),
            reason="Phase E ledger opening balance",
            idempotency_key=f"phase-e-backfill-v1:opening:{row.pk}",
            base_delta=row.base_days,
            carry_over_delta=row.carry_over_days,
            manual_adjustment_delta=row.manual_adjustment,
        )

    for req in Request.objects.using(db).filter(
        leave_type__counts_against_balance=True,
        status__in=["PENDING", "ESCALATED", "APPROVED", "WITHDRAWAL_PENDING"],
    ).select_related("policy_version").order_by("pk").iterator(chunk_size=500):
        policy_values = req.policy_version.values if req.policy_version_id else {}
        calendar = policy_values.get("policy.leave_calendar", "jalali")
        day_weights = {}
        current = req.start_date
        while current <= req.end_date:
            year = from_gregorian(current)[0] if calendar == "jalali" else current.year
            day_weights[year] = day_weights.get(year, 0) + 1
            current += dt.timedelta(days=1)
        if not day_weights:
            day_weights[req.start_date.year] = 1
        weighted_years = sorted(day_weights)
        total_weight = sum(day_weights.values())
        shares = {}
        allocated = Decimal("0")
        for year in weighted_years[:-1]:
            share = (
                req.working_days * day_weights[year] / total_weight
            ).quantize(Decimal("0.1"), ROUND_HALF_UP)
            shares[year] = share
            allocated += share
        shares[weighted_years[-1]] = req.working_days - allocated

        for year, amount in shares.items():
            entitlement_id = entitlement_ids.get((req.employee_id, req.leave_type_id, year))
            if entitlement_id is None:
                continue
            state = states[entitlement_id]
            before = _snapshot(state)
            is_reserved = req.status in ("PENDING", "ESCALATED")
            state["reserved" if is_reserved else "used"] += amount
            after = _snapshot(state)
            Event.objects.using(db).create(
                entitlement_id=entitlement_id,
                request_id=req.pk,
                kind="reservation" if is_reserved else "approval",
                before=before,
                after=after,
                reason="Phase E ledger request backfill",
                idempotency_key=f"phase-e-backfill-v1:request:{req.pk}:year:{year}",
                reserved_delta=amount if is_reserved else Decimal("0"),
                used_delta=Decimal("0") if is_reserved else amount,
            )


def reverse_backfill(apps, schema_editor):
    Event = apps.get_model("leave", "EntitlementEvent")
    Event.objects.using(schema_editor.connection.alias).filter(
        idempotency_key__startswith="phase-e-backfill-v1:",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0006_entitlement_ledger"),
    ]

    operations = [
        migrations.RunPython(backfill_entitlement_journal, reverse_backfill),
    ]
