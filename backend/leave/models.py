"""مدل‌های هسته. مهاجرت‌ها باید روی ماشین دارای Django تولید و بازبینی شوند (makemigrations)."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from zsh_core import workflow as wf

STATUS_CHOICES = [(s, s) for s in (wf.PENDING, wf.ESCALATED, wf.APPROVED, wf.REJECTED,
                                   wf.CANCELLED, wf.WITHDRAWAL_PENDING)]


class Company(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)


class Department(models.Model):
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "code"], name="uniq_dept_code_in_company")]


class EmployeeProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.PROTECT)
    personnel_code = models.CharField(max_length=32)
    manager = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="direct_reports")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    is_employee = models.BooleanField(default=True)   # حساب سرویس/مهمان = False

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "personnel_code"], name="uniq_personnel_code"),
            models.CheckConstraint(condition=~Q(manager=models.F("id")), name="manager_not_self"),
        ]


class LeaveType(models.Model):
    key = models.CharField(max_length=32, unique=True)
    label_fa = models.CharField(max_length=128)
    label_en = models.CharField(max_length=128, blank=True)
    color = models.CharField(max_length=7, default="#3b6ea5")
    icon = models.CharField(max_length=16, blank=True)
    counts_against_balance = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=True)
    requires_note = models.BooleanField(default=False)
    requires_replacement = models.BooleanField(default=False)
    employee_requestable = models.BooleanField(default=True)
    confidential = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(confidential=False) | Q(employee_requestable=False),
            name="confidential_not_self_requestable")]


class LeaveEntitlement(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    year = models.IntegerField()                         # سال مرخصی طبق سیاست (شمسی/میلادی)
    base_days = models.DecimalField(max_digits=5, decimal_places=1)
    carry_over_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    manual_adjustment = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["employee", "leave_type", "year"],
                                               name="uniq_entitlement")]


class EntitlementEvent(models.Model):
    """تاریخچه سهمیه؛ append-only."""
    entitlement = models.ForeignKey(LeaveEntitlement, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=32)            # adjust | rollover | import | set
    before = models.JSONField()
    after = models.JSONField()
    reason = models.TextField()
    idempotency_key = models.CharField(max_length=128, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class LeaveRequest(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.PROTECT, related_name="requests")
    manager_snapshot = models.ForeignKey(EmployeeProfile, null=True, blank=True,
                                         on_delete=models.PROTECT, related_name="+")
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    working_days = models.DecimalField(max_digits=5, decimal_places=1)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, db_index=True)
    reason = models.TextField(blank=True)
    replacement = models.ForeignKey(EmployeeProfile, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="amendments")
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["employee", "status"]),
            models.Index(fields=["manager_snapshot", "status"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(start_date__lte=models.F("end_date")), name="start_le_end"),
            models.CheckConstraint(condition=Q(working_days__gt=0), name="working_days_positive"),
            models.CheckConstraint(condition=Q(status__in=[c[0] for c in STATUS_CHOICES]),
                                   name="valid_status"),
            models.CheckConstraint(condition=~Q(replacement=models.F("employee")),
                                   name="replacement_not_self"),
            # فقط یک اصلاحیه غیرپایانی برای هر درخواست اصلی
            models.UniqueConstraint(
                fields=["supersedes"], name="one_active_amendment",
                condition=Q(supersedes__isnull=False) & ~Q(status__in=[wf.REJECTED, wf.CANCELLED])),
        ]


class _AppendOnly(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError("رکورد حسابرسی/تاریخچه قابل ویرایش نیست")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("رکورد حسابرسی/تاریخچه قابل حذف نیست")


class LeaveRequestEvent(_AppendOnly):
    request = models.ForeignKey(LeaveRequest, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    origin = models.CharField(max_length=16)          # employee | manager | hr | system
    event = models.CharField(max_length=32)
    from_status = models.CharField(max_length=24, blank=True)
    to_status = models.CharField(max_length=24)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(_AppendOnly):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    origin = models.CharField(max_length=16)
    action = models.CharField(max_length=64)
    entity = models.CharField(max_length=64)
    entity_id = models.CharField(max_length=64)
    before = models.JSONField(null=True)              # بدون متن آزاد/اطلاعات پزشکی
    after = models.JSONField(null=True)
    reason = models.TextField(blank=True)
    result = models.CharField(max_length=16, default="ok")
    created_at = models.DateTimeField(auto_now_add=True)


class SystemSetting(models.Model):
    """تنظیمات قابل ویرایش از داشبورد مدیریت؛ مقدار فقط با zsh_core.settings_schema اعتبارسنجی و ذخیره می‌شود."""
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField(null=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)


class PublicHoliday(models.Model):
    """تعطیلی ثبت‌شده دستی (شمسی). jalali_year خالی = سالانه."""
    scope = models.CharField(max_length=64, default="*")      # '*' ملی؛ یا کد شرکت/منطقه
    jalali_year = models.IntegerField(null=True, blank=True)
    jalali_month = models.PositiveSmallIntegerField()
    jalali_day = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=200)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "jalali_year", "jalali_month", "jalali_day"],
                                    name="uniq_holiday_exact", nulls_distinct=False),
            models.CheckConstraint(condition=Q(jalali_month__gte=1, jalali_month__lte=12,
                                               jalali_day__gte=1, jalali_day__lte=31),
                                   name="holiday_month_day_range"),
        ]


class PublicHolidayHistory(_AppendOnly):
    holiday_id = models.BigIntegerField()          # بدون FK تا با حذف تعطیلی تاریخچه بماند
    action = models.CharField(max_length=16)       # create | update | delete
    before = models.JSONField(null=True)
    after = models.JSONField(null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
