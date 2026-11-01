"""ماشین وضعیت درخواست مرخصی (تابع خالص). هیچ I/O ندارد؛ لایه سرویس نتیجه را در تراکنش ذخیره می‌کند."""
from __future__ import annotations

from dataclasses import dataclass

PENDING, ESCALATED, APPROVED = "PENDING", "ESCALATED", "APPROVED"
REJECTED, CANCELLED, WITHDRAWAL_PENDING = "REJECTED", "CANCELLED", "WITHDRAWAL_PENDING"
TERMINAL = frozenset({REJECTED, CANCELLED})

# نقش‌های کنشگر
EMPLOYEE, MANAGER, HR, SYSTEM = "employee", "manager", "hr", "system"


class WorkflowError(Exception):
    code = "workflow_error"


class InvalidTransition(WorkflowError):
    code = "invalid_transition"      # HTTP 409/400


class ConflictError(WorkflowError):
    code = "conflict"                # HTTP 409


class PermissionDenied(WorkflowError):
    code = "forbidden"               # HTTP 403/404


class ValidationError(WorkflowError):
    code = "validation"              # HTTP 422


@dataclass(frozen=True)
class Context:
    actor: str
    reason: str = ""
    requires_approval: bool = True
    confidential: bool = False
    has_manager: bool = True
    manager_away: bool = False
    amendment_in_flight: bool = False   # یک درخواست supersedes غیرپایانی وجود دارد
    is_amendment: bool = False          # این درخواست خودش اصلاحیه‌ای برای اصل است


def initial_status(ctx: Context) -> str:
    """وضعیت اولیه هنگام ثبت."""
    if not ctx.requires_approval or (ctx.actor == HR):
        return APPROVED                      # ثبت HR یا نوع بدون تأیید
    if ctx.confidential:
        raise PermissionDenied("نوع محرمانه فقط توسط HR ثبت می‌شود")
    if not ctx.has_manager or ctx.manager_away:
        return ESCALATED
    return PENDING


def _deciders(ctx: Context) -> None:
    if ctx.actor not in (MANAGER, HR):
        raise PermissionDenied("فقط مدیر مستقیم یا HR می‌تواند تصمیم بگیرد")
    if ctx.confidential and ctx.actor != HR:
        raise PermissionDenied("تصمیم درباره نوع محرمانه فقط با HR است")


def transition(status: str, event: str, ctx: Context) -> str:
    """وضعیت جدید را برمی‌گرداند یا استثنا می‌دهد. event یکی از:
    approve, reject, cancel, escalate, request_withdraw, approve_withdraw,
    reject_withdraw, hr_cancel
    """
    if status in TERMINAL:
        raise InvalidTransition(f"وضعیت پایانی {status} قابل تغییر نیست")

    if event == "approve":
        if status == PENDING:
            _deciders(ctx)
            if ctx.actor == MANAGER and ctx.manager_away:
                pass  # مدیر خودش تصمیم می‌گیرد؛ غیبت فقط مسیر ثبت را عوض می‌کند
            return APPROVED
        if status == ESCALATED:
            if ctx.actor != HR:
                raise PermissionDenied("درخواست ارجاع‌شده را فقط HR تصمیم می‌گیرد")
            return APPROVED
        raise InvalidTransition(f"approve از {status} مجاز نیست")

    if event == "reject":
        if status not in (PENDING, ESCALATED):
            raise InvalidTransition(f"reject از {status} مجاز نیست")
        _deciders(ctx)
        if status == ESCALATED and ctx.actor != HR:
            raise PermissionDenied("درخواست ارجاع‌شده را فقط HR تصمیم می‌گیرد")
        if not ctx.reason.strip():
            raise ValidationError("درج دلیل رد الزامی است")
        return REJECTED

    if event == "cancel":  # لغو توسط کارمند، فقط پیش از تأیید
        if ctx.actor not in (EMPLOYEE, HR):
            raise PermissionDenied("فقط کارمند صاحب درخواست یا HR")
        if status in (PENDING, ESCALATED):
            return CANCELLED
        raise InvalidTransition("درخواست تأییدشده با «درخواست لغو» لغو می‌شود")

    if event == "escalate":  # فقط سیستم؛ شرط status=PENDING در UPDATE شرطی DB تکرار می‌شود
        if ctx.actor != SYSTEM:
            raise PermissionDenied("ارجاع خودکار فقط توسط سیستم")
        if status != PENDING:
            raise InvalidTransition("فقط PENDING ارجاع می‌شود")
        return ESCALATED

    if event == "request_withdraw":
        if status != APPROVED:
            raise InvalidTransition("لغو فقط برای مرخصی تأییدشده درخواست می‌شود")
        if ctx.actor not in (EMPLOYEE, HR):
            raise PermissionDenied("فقط کارمند یا HR")
        if ctx.confidential and ctx.actor != HR:
            raise PermissionDenied("نوع محرمانه فقط با HR")
        if ctx.amendment_in_flight:
            raise ConflictError("تا پایان اصلاح جاری، درخواست لغو ممکن نیست")
        return WITHDRAWAL_PENDING

    if event == "approve_withdraw":
        if status != WITHDRAWAL_PENDING:
            raise InvalidTransition("وضعیت باید WITHDRAWAL_PENDING باشد")
        _deciders(ctx)
        return CANCELLED

    if event == "reject_withdraw":
        if status != WITHDRAWAL_PENDING:
            raise InvalidTransition("وضعیت باید WITHDRAWAL_PENDING باشد")
        _deciders(ctx)
        if not ctx.reason.strip():
            raise ValidationError("درج دلیل رد الزامی است")
        return APPROVED

    if event == "hr_cancel":
        if ctx.actor != HR:
            raise PermissionDenied("فقط HR")
        if not ctx.reason.strip():
            raise ValidationError("دلیل الزامی است")
        return CANCELLED

    raise InvalidTransition(f"رویداد ناشناخته: {event}")


def can_start_amendment(status: str, ctx: Context) -> None:
    """ایجاد درخواست اصلاحی برای مرخصی تأییدشده؛ فقط یک اصلاح فعال."""
    if status != APPROVED:
        raise InvalidTransition("فقط مرخصی تأییدشده قابل اصلاح است")
    if ctx.amendment_in_flight:
        raise ConflictError("یک اصلاح فعال برای این درخواست وجود دارد")
    if ctx.confidential and ctx.actor != HR:
        raise PermissionDenied("نوع محرمانه فقط با HR")


def resolve_amendment(original_status: str, approved: bool) -> tuple[str, str]:
    """نتیجه تأیید/رد اصلاحیه → (وضعیت اصل، وضعیت اصلاحیه). دو پیامد در یک تراکنش اعمال شوند."""
    if original_status not in (APPROVED,):
        raise InvalidTransition("اصل باید APPROVED باشد")
    return (CANCELLED, APPROVED) if approved else (APPROVED, REJECTED)
