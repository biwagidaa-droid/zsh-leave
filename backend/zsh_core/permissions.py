"""تصمیم دسترسی و حذف اطلاعات حساس (redaction) — تک‌نقطه‌ای و خالص.

هر خروجی به کلاینت (API، تقویم، اعلان، خروجی فایل) باید از این توابع بگذرد.
قاعده کلی: خارج از دامنه → None (در API به 404 تبدیل می‌شود، نه 403، تا وجود رکورد فاش نشود).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Mapping

EMPLOYEE, MANAGER, HR, ADMIN, EXEC = "employee", "manager", "hr", "admin", "exec"
NEUTRAL_LABEL = "غایب"


@dataclass(frozen=True)
class Viewer:
    user_id: int
    roles: frozenset = frozenset()
    employee_id: int | None = None
    hr_company_ids: frozenset | None = frozenset()   # None = همه شرکت‌ها؛ خالی = هیچ

    def is_hr_for(self, company_id: int) -> bool:
        if HR not in self.roles:
            return False
        return self.hr_company_ids is None or company_id in self.hr_company_ids


@dataclass(frozen=True)
class RequestFacts:
    id: int
    employee_id: int
    company_id: int
    manager_snapshot_id: int | None
    confidential: bool
    status: str
    start: dt.date
    end: dt.date
    type_key: str
    type_label: str
    reason: str = ""
    decision_comment: str = ""
    replacement_id: int | None = None
    working_days: str = ""


def _is_owner(v: Viewer, f: RequestFacts) -> bool:
    return v.employee_id is not None and v.employee_id == f.employee_id


def _is_manager(v: Viewer, f: RequestFacts) -> bool:
    return v.employee_id is not None and f.manager_snapshot_id == v.employee_id


def can_view_request(v: Viewer, f: RequestFacts) -> bool:
    """مدیر سامانه و گزارش‌خوان ارشد به رکورد فردی دسترسی ندارند (تفکیک وظایف)."""
    return _is_owner(v, f) or _is_manager(v, f) or v.is_hr_for(f.company_id)


def can_decide(v: Viewer, f: RequestFacts) -> bool:
    """مجوز نقش؛ مجاز بودن «وضعیت» را ماشین وضعیت (workflow) تعیین می‌کند."""
    if v.is_hr_for(f.company_id):
        return True
    return _is_manager(v, f) and not f.confidential and not _is_owner(v, f)


def _sees_confidential_detail(v: Viewer, f: RequestFacts) -> bool:
    return v.is_hr_for(f.company_id)


def serialize_request(v: Viewer, f: RequestFacts, settings: Mapping[str, Any]) -> dict | None:
    if not can_view_request(v, f):
        return None
    base = {"id": f.id, "employeeId": f.employee_id, "status": f.status,
            "start": f.start.isoformat(), "end": f.end.isoformat(), "workingDays": f.working_days}
    if not f.confidential:
        return {**base, "type": f.type_key, "typeLabel": f.type_label, "reason": f.reason,
                "decisionComment": f.decision_comment, "replacementId": f.replacement_id,
                "canDecide": can_decide(v, f)}
    owner_may = _is_owner(v, f) and settings.get("privacy.employee_sees_own_confidential_type", False)
    if _sees_confidential_detail(v, f):
        return {**base, "type": f.type_key, "typeLabel": f.type_label, "reason": f.reason,
                "decisionComment": f.decision_comment, "replacementId": f.replacement_id,
                "canDecide": True}
    out = {**base, "type": None, "typeLabel": NEUTRAL_LABEL, "reason": None,
           "decisionComment": None, "replacementId": None, "canDecide": False}
    if owner_may:   # فقط نام نوع؛ هرگز دلیل/یادداشت
        out.update(type=f.type_key, typeLabel=f.type_label)
    return out


def calendar_event(v: Viewer, f: RequestFacts, settings: Mapping[str, Any]) -> dict:
    """رویداد تقویم/تایم‌لاین. دامنه دید (چه کسی کدام فرد را ببیند) در لایه انتخاب‌گر اعمال می‌شود؛
    اینجا فقط برچسب حساس‌زدایی می‌شود."""
    label = NEUTRAL_LABEL
    if not f.confidential:
        if v.is_hr_for(f.company_id) or _is_owner(v, f) or _is_manager(v, f) \
                or settings.get("privacy.peers_see_leave_type", False):
            label = f.type_label
    elif v.is_hr_for(f.company_id):
        label = f.type_label
    return {"employeeId": f.employee_id, "start": f.start.isoformat(), "end": f.end.isoformat(),
            "status": f.status, "label": label}


def notification_text(event: str, f: RequestFacts, recipient: Viewer) -> str:
    """متن اعلان/ایمیل. هرگز نوع محرمانه، دلیل، یادداشت یا اطلاعات پزشکی ندارد."""
    templates = {
        "submitted": "درخواست مرخصی جدیدی برای تصمیم‌گیری ثبت شد.",
        "approved": "درخواست مرخصی شما تأیید شد.",
        "rejected": "درخواست مرخصی شما رد شد.",
        "escalated": "درخواستی به منابع انسانی ارجاع شد.",
        "cancelled": "یک مرخصی لغو شد.",
        "replacement_assigned": "شما به‌عنوان جانشین انتخاب شده‌اید.",
        "replacement_cancelled": "جانشینی شما لغو شد.",
    }
    base = templates.get(event, "رویداد جدیدی در سامانه ثبت شد.")
    if f.confidential or recipient.employee_id == f.replacement_id:
        return base                                   # جانشین و محرمانه: بدون جزئیات
    return f"{base} ({f.start.isoformat()} تا {f.end.isoformat()})"


def visible_balance_types(v: Viewer, company_id: int, types: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """نام نوع محرمانه خودش حساس است؛ برای غیر HR از فهرست حذف می‌شود."""
    if v.is_hr_for(company_id):
        return list(types)
    return [t for t in types if not t.get("confidential")]
