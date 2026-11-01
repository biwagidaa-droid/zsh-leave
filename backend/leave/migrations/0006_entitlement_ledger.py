import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0005_operational_workflow"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="entitlementevent",
            name="base_delta",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="entitlementevent",
            name="carry_over_delta",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="entitlementevent",
            name="manual_adjustment_delta",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="entitlementevent",
            name="reserved_delta",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="entitlementevent",
            name="used_delta",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=8),
        ),
        migrations.AddField(
            model_name="entitlementevent",
            name="request",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entitlement_events",
                to="leave.leaverequest",
            ),
        ),
        migrations.AddField(
            model_name="entitlementevent",
            name="reversal_of",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversal",
                to="leave.entitlementevent",
            ),
        ),
        migrations.AddIndex(
            model_name="entitlementevent",
            index=models.Index(
                fields=["entitlement", "created_at"], name="ent_event_ent_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="entitlementevent",
            index=models.Index(fields=["request", "kind"], name="ent_event_req_kind_idx"),
        ),
    ]
