"""لایه سرویس: تنها نقطه تغییر وضعیت درخواست‌ها. تراکنش + قفل ردیف؛ منطق از zsh_core."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from zsh_core import workflow as wf
from .models import (AuditEvent, EmployeeProfile, LeaveRequest, LeaveRequestEvent, LeaveType)


class ServiceError(Exception):
    pass


ACTIVE = [wf.PENDING, wf.ESCALATED, wf.APPROVED, wf.WITHDRAWAL_PENDING]


def _origin(actor_role: str) -> str:
    return actor_role  # employee | manager | hr | system


def _log(req, user, role, event, from_s, to_s, reason=""):
    LeaveRequestEvent.objects.create(request=req, actor=user, origin=_origin(role), event=event,
                                     from_status=from_s, to_status=to_s, reason=reason)
    AuditEvent.objects.create(actor=user, origin=_origin(role), action=f"leave.{event}",
                              entity="LeaveRequest", entity_id=str(req.pk),
                              before={"status": from_s}, after={"status": to_s},
                              reason="" if req.leave_type.confidential else reason)


def _validate_new(employee: EmployeeProfile, ltype: LeaveType, start, end, days: Decimal,
                  replacement, role: str, policy_allow_past: bool):
    if not ltype.enabled:
        raise wf.ValidationError("این نوع مرخصی فعال نیست")
    if role == wf.EMPLOYEE and not ltype.employee_requestable:
        raise wf.PermissionDenied("این نوع مرخصی را فقط HR ثبت می‌کند")
    if not employee.is_employee or (employee.end_date and employee.end_date < dt.date.today()):
        raise wf.ValidationError("کارمند فعال نیست")
    if start > end:
        raise wf.ValidationError("تاریخ شروع نباید بعد از پایان باشد")
    if days <= 0:
        raise wf.ValidationError("تعداد روز باید مثبت باشد")
    if (end - start).days + 1 < days:
        raise wf.ValidationError("تعداد روز از طول بازه بیشتر است")
    if end < dt.date.today() and role != wf.HR and not policy_allow_past:
        raise wf.ValidationError("ثبت مرخصی گذشته مجاز نیست")
    if ltype.requires_replacement:
        if replacement is None:
            raise wf.ValidationError("انتخاب جانشین الزامی است")
        if replacement.pk == employee.pk or not replacement.is_employee:
            raise wf.ValidationError("جانشین نامعتبر است")


@transaction.atomic
def submit_request(*, user, role: str, employee: EmployeeProfile, leave_type: LeaveType,
                   start, end, working_days: Decimal, reason: str = "",
                   replacement: EmployeeProfile | None = None,
                   manager_away: bool = False, policy_allow_past: bool = False) -> LeaveRequest:
    # قفل ردیف کارمند: ثبت‌های هم‌زمان یک کارمند سریالی می‌شوند (جلوگیری از هم‌پوشانی)
    EmployeeProfile.objects.select_for_update().get(pk=employee.pk)
    _validate_new(employee, leave_type, start, end, working_days, replacement, role, policy_allow_past)
    overlap = LeaveRequest.objects.filter(employee=employee, status__in=ACTIVE,
                                          start_date__lte=end, end_date__gte=start)
    if overlap.exists():
        raise wf.ConflictError("با درخواست دیگری برای همین کارمند هم‌پوشانی دارد")
    ctx = wf.Context(actor=role, requires_approval=leave_type.requires_approval,
                     confidential=leave_type.confidential,
                     has_manager=employee.manager_id is not None, manager_away=manager_away)
    status = wf.initial_status(ctx)
    req = LeaveRequest.objects.create(
        employee=employee, manager_snapshot=employee.manager, leave_type=leave_type,
        start_date=start, end_date=end, working_days=working_days, status=status,
        reason=reason, replacement=replacement,
        decided_by=user if status == wf.APPROVED else None,
        decided_at=timezone.now() if status == wf.APPROVED else None)
    _log(req, user, role, "submit", "", status, "")
    return req


@transaction.atomic
def apply_event(*, request_id: int, user, role: str, event: str, reason: str = "") -> LeaveRequest:
    req = LeaveRequest.objects.select_for_update().select_related("leave_type").get(pk=request_id)
    in_flight = req.amendments.exclude(status__in=[wf.REJECTED, wf.CANCELLED]).exists()
    ctx = wf.Context(actor=role, reason=reason, confidential=req.leave_type.confidential,
                     amendment_in_flight=in_flight)
    old = req.status
    new = wf.transition(old, event, ctx)       # استثنا → تراکنش برمی‌گردد
    req.status = new
    if event in ("approve", "reject", "approve_withdraw", "reject_withdraw", "hr_cancel"):
        req.decided_by, req.decided_at, req.decision_comment = user, timezone.now(), reason
    req.save()
    _log(req, user, role, event, old, new, reason)
    return req


def escalate_overdue(request_ids: list[int]) -> int:
    """Job ارجاع: بروزرسانی شرطی تا تصمیم هم‌زمان مدیر بازنویسی نشود."""
    n = 0
    for rid in request_ids:
        with transaction.atomic():
            changed = LeaveRequest.objects.filter(pk=rid, status=wf.PENDING).update(status=wf.ESCALATED)
            if changed:
                req = LeaveRequest.objects.select_related("leave_type").get(pk=rid)
                _log(req, None, wf.SYSTEM, "escalate", wf.PENDING, wf.ESCALATED, "")
                n += 1
    return n
