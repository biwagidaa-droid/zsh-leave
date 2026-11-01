from __future__ import annotations

import csv
import datetime as dt
import io
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from zsh_core import settings_schema
from zsh_core.permissions import HR as POLICY_HR, Viewer, visible_balance_types
from . import admin_services
from .authorization import (
    MANAGE_GLOBAL_LEAVE_TYPES, authorization_context, has_permission, hr_operation_employees,
    scoped_employees, scoped_hr_employees, scoped_hr_leave_requests,
)
from .entitlement_services import (
    EntitlementLedgerError,
    adjust_entitlement,
    create_entitlement,
    entitlement_balance,
)
from .invitation_services import (
    InvitationError,
    invite_employee,
    normalize_email,
    synchronize_employment_access,
)
from .models import (
    AuditEvent,
    BradfordNote,
    Company,
    ContractPeriod,
    Department,
    EmployeeProfile,
    LeaveEntitlement,
    LeaveRequestAttachment,
    LeaveRequest,
    LeaveRequestEvent,
    LeaveType,
    NotificationRead,
    RoleAssignment,
    SystemSetting,
)
from .throttling import rate_limited

User = get_user_model()


def _failure(code: str, message: str, status: int, fields: dict | None = None) -> Response:
    body = {"code": code, "message_fa": message}
    if fields:
        body["fields"] = fields
    return Response(body, status=status)


def _context(request):
    return authorization_context(request.user)


def _admin(context) -> bool:
    return context.has_role("admin")


def _hr(context, employee: EmployeeProfile) -> bool:
    return context.has_scope(
        "hr", company_id=employee.company_id, site_id=employee.site_id,
        department_id=employee.department_id, employee_id=employee.pk,
    )


def _employee_rows(context):
    rows = EmployeeProfile.objects.select_related(
        "user", "company", "department", "manager__user",
    ).filter(is_employee=True)
    if _admin(context):
        return rows
    return rows.filter(pk__in=scoped_employees(context).values("pk"))


def _employee_json(employee: EmployeeProfile) -> dict:
    return {
        "id": employee.pk,
        "userId": employee.user_id,
        "displayName": employee.user.get_full_name().strip() or employee.user.get_username(),
        "personnelCode": employee.personnel_code,
        "companyId": employee.company_id,
        "companyName": employee.company.name,
        "departmentName": employee.department.name if employee.department_id else "",
        "positionName": "",
        "managerName": (
            employee.manager.user.get_full_name().strip() or employee.manager.user.get_username()
            if employee.manager_id else None
        ),
        "startDate": employee.start_date.isoformat(),
        "endDate": employee.end_date.isoformat() if employee.end_date else None,
        "isActive": employee.end_date is None,
        "accountStatus": employee.account_status,
    }


def _leave_type_json(item: LeaveType) -> dict:
    return {
        "id": item.pk, "key": item.key, "labelFa": item.label_fa, "color": item.color,
        "countsAgainstBalance": item.counts_against_balance, "requiresApproval": item.requires_approval,
        "requiresNote": item.requires_note, "requiresReplacement": item.requires_replacement,
        "employeeRequestable": item.employee_requestable, "confidential": item.confidential,
        "enabled": item.enabled, "sortOrder": item.sort_order,
    }


def _entitlement_json(item: LeaveEntitlement) -> dict:
    return {
        "id": item.pk, "employeeId": item.employee_id,
        "employeeName": item.employee.user.get_full_name().strip() or item.employee.user.get_username(),
        "leaveTypeKey": item.leave_type.key, "leaveTypeLabel": item.leave_type.label_fa,
        "year": item.year, "base": str(item.base_days), "carryOver": str(item.carry_over_days),
        "adjustment": str(item.manual_adjustment),
    }


def _balance_json(item: LeaveEntitlement) -> dict:
    balance = entitlement_balance(item)
    return {
        **_entitlement_json(item),
        "total": str(balance["total"]), "used": str(balance["used"]),
        "pending": str(balance["reserved"]), "remaining": str(balance["remaining"]),
        "usable": str(balance["available"]),
    }


def _visible_entitlement_rows(context, rows) -> list[LeaveEntitlement]:
    visible = []
    for item in rows:
        employee = item.employee
        is_scoped_hr = _hr(context, employee)
        viewer = Viewer(
            user_id=context.user.pk,
            roles=frozenset({POLICY_HR}) if is_scoped_hr else frozenset(),
            hr_company_ids=frozenset({employee.company_id}) if is_scoped_hr else frozenset(),
        )
        if visible_balance_types(
            viewer,
            employee.company_id,
            [{"id": item.leave_type_id, "confidential": item.leave_type.confidential}],
        ):
            visible.append(item)
    return visible


@api_view(["GET", "POST", "PATCH"])
def leave_types(request, type_id: int | None = None):
    context = _context(request)
    if request.method == "GET":
        rows = LeaveType.objects.all()
        if context.has_role("hr") and not has_permission(context, MANAGE_GLOBAL_LEAVE_TYPES):
            rows = rows.filter(enabled=True)
        elif not has_permission(context, MANAGE_GLOBAL_LEAVE_TYPES):
            rows = rows.filter(enabled=True, employee_requestable=True)
        return Response([_leave_type_json(item) for item in rows.order_by("sort_order", "pk")])

    if not has_permission(context, MANAGE_GLOBAL_LEAVE_TYPES):
        return _failure("permission_denied", "مدیریت انواع مرخصی مجاز نیست", 403)
    data = request.data
    allowed = {
        "key", "labelFa", "color", "countsAgainstBalance", "requiresApproval", "requiresNote",
        "requiresReplacement", "employeeRequestable", "confidential", "enabled", "sortOrder",
        "reason",
    }
    if not isinstance(data, dict) or not data or set(data) - allowed:
        return _failure("invalid_payload", "فیلدهای نوع مرخصی معتبر نیست", 400)
    try:
        item = admin_services.save_leave_type(
            actor=request.user,
            leave_type_id=type_id,
            data=data,
            reason=data.get("reason", ""),
            correlation_id=request.headers.get("X-Correlation-ID", ""),
        )
    except LeaveType.DoesNotExist:
        raise Http404
    except PermissionDenied:
        return _failure("permission_denied", "مدیریت انواع مرخصی مجاز نیست", 403)
    except (ValidationError, IntegrityError, TypeError, ValueError):
        return _failure("invalid_leave_type", "اطلاعات نوع مرخصی معتبر نیست", 400)
    return Response(_leave_type_json(item), status=201 if type_id is None else 200)


@api_view(["GET"])
def balances(request):
    context = _context(request)
    try:
        year = int(request.query_params.get("year", ""))
        employee_id = int(request.query_params["employee"]) if request.query_params.get("employee") else context.employee_id
    except ValueError:
        return _failure("invalid_filter", "سال یا شناسه کارمند معتبر نیست", 400)
    if employee_id is None:
        return _failure("employee_profile_required", "پرونده کارمندی لازم است", 403)
    employee = scoped_employees(context).select_related(
        "company", "site", "department",
    ).filter(pk=employee_id).first()
    if employee is None:
        raise Http404
    entries = LeaveEntitlement.objects.select_related("employee__user", "leave_type").filter(
        employee=employee, year=year, leave_type__counts_against_balance=True,
    ).order_by("leave_type__sort_order", "pk")
    from .entitlement_services import EntitlementReconciliationError

    try:
        visible_entries = _visible_entitlement_rows(context, entries)
        return Response([_balance_json(item) for item in visible_entries])
    except EntitlementReconciliationError:
        return _failure("entitlement_reconciliation", "دفترکل سهمیه نیازمند بررسی است", 409)


@api_view(["GET"])
def entitlements(request):
    context = _context(request)
    if not context.has_role("hr"):
        return _failure("permission_denied", "مشاهده سهمیه‌های کارکنان مجاز نیست", 403)
    try:
        year = int(request.query_params.get("year", ""))
    except ValueError:
        return _failure("invalid_year", "سال معتبر نیست", 400)
    employee_ids = scoped_hr_employees(context).values("pk")
    rows = LeaveEntitlement.objects.select_related(
        "employee__user", "employee__company", "employee__site", "employee__department", "leave_type",
    ).filter(employee_id__in=employee_ids, year=year).order_by(
        "employee__user__last_name", "employee__user__first_name", "leave_type__sort_order",
    )
    return Response([
        _entitlement_json(item) for item in _visible_entitlement_rows(context, rows)
    ])


@api_view(["POST"])
def entitlement_adjustment(request, entitlement_id: int):
    context = _context(request)
    if not (context.has_role("hr") or _admin(context)):
        return _failure("permission_denied", "اصلاح سهمیه مجاز نیست", 403)
    data = request.data
    if not isinstance(data, dict) or set(data) != {"days", "reason"}:
        return _failure("invalid_payload", "روز و دلیل الزامی است", 400)
    item = LeaveEntitlement.objects.select_related("employee").filter(pk=entitlement_id).first()
    if item is None or not hr_operation_employees(context).filter(pk=item.employee_id).exists():
        raise Http404
    try:
        event = adjust_entitlement(
            entitlement_id=item.pk, component="manual_adjustment", delta=data["days"],
            actor=request.user, reason=data["reason"],
            idempotency_key=request.headers.get("Idempotency-Key") or str(uuid4()),
        )
    except EntitlementLedgerError as exc:
        return _failure("invalid_adjustment", str(exc), 400)
    item.refresh_from_db()
    return Response(_entitlement_json(item))


def _import_preview(csv_text: str, context) -> tuple[dict, list[tuple]]:
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        required = {"personnel_code", "type", "year", "days"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            return {
                "dryRun": True,
                "rows": [{
                    "line": 1, "employee": "", "type": "", "year": 0,
                    "days": "", "ok": False,
                    "error": "سرستون‌های personnel_code,type,year,days الزامی هستند",
                }],
                "accepted": 0, "rejected": 1,
            }, []
        parsed = []
        rows = []
        employees = {
            e.personnel_code: e
            for e in hr_operation_employees(context).select_related("user", "company")
        }
        types = {t.key: t for t in LeaveType.objects.filter(enabled=True)}
        for line, raw in enumerate(reader, 2):
            code, key = (raw.get("personnel_code") or "").strip(), (raw.get("type") or "").strip()
            try:
                row_year = int(raw.get("year", ""))
                days = Decimal((raw.get("days") or "").strip())
                if not days.is_finite() or days <= 0 or days * 10 != (days * 10).to_integral_value():
                    raise ValueError
                employee, leave_type = employees.get(code), types.get(key)
                if not employee or not leave_type:
                    raise ValueError
                if LeaveEntitlement.objects.filter(employee=employee, leave_type=leave_type, year=row_year).exists():
                    raise ValueError
                parsed.append((line, employee, leave_type, row_year, days))
                rows.append({"line": line, "employee": employee.user.get_full_name() or employee.user.username,
                             "type": leave_type.key, "year": row_year, "days": str(days), "ok": True})
            except (ValueError, TypeError, InvalidOperation):
                rows.append({"line": line, "employee": code, "type": key, "year": 0,
                             "days": raw.get("days", ""), "ok": False,
                             "error": "اطلاعات یا دسترسی این ردیف معتبر نیست"})
        return {
            "dryRun": True, "rows": rows,
            "accepted": sum(row["ok"] for row in rows),
            "rejected": sum(not row["ok"] for row in rows),
        }, parsed
    except csv.Error:
        return {"dryRun": True, "rows": [], "accepted": 0, "rejected": 1}, []


@rate_limited("bulk_import")
@api_view(["POST"])
def entitlement_import(request):
    context = _context(request)
    if not (context.has_role("hr") or _admin(context)):
        return _failure("permission_denied", "ورود گروهی سهمیه مجاز نیست", 403)
    data = request.data
    if not isinstance(data, dict) or set(data) != {"csv"} or not isinstance(data["csv"], str):
        return _failure("invalid_payload", "متن CSV الزامی است", 400)
    dry_run = request.query_params.get("dry_run") == "1"
    preview, valid = _import_preview(data["csv"], context)
    preview["dryRun"] = dry_run
    if not dry_run and preview["rejected"] == 0:
        try:
            with transaction.atomic():
                current_context = _context(request)
                if not (current_context.has_role("hr") or _admin(current_context)):
                    return _failure("permission_denied", "ورود گروهی سهمیه مجاز نیست", 403)
                employee_ids = {employee.pk for _, employee, _, _, _ in valid}
                current_employees = {
                    employee.pk: employee
                    for employee in hr_operation_employees(current_context).filter(
                        pk__in=employee_ids,
                    ).select_related("user", "company")
                }
                if set(current_employees) != employee_ids:
                    raise EntitlementLedgerError("دامنه ورود گروهی دیگر معتبر نیست")
                for line, employee, leave_type, year, days in valid:
                    create_entitlement(
                        employee=current_employees[employee.pk], leave_type=leave_type,
                        year=year, base_days=days,
                        actor=request.user, reason="ورود گروهی سهمیه",
                        idempotency_key=f"import:{request.user.pk}:{uuid4()}:{line}",
                    )
        except (EntitlementLedgerError, IntegrityError) as exc:
            return _failure("entitlement_import_failed", str(exc), 409)
    return Response(preview)


@rate_limited("employee_search")
@api_view(["GET", "POST", "PATCH"])
def employees(request, employee_id: int | None = None):
    context = _context(request)
    rows = _employee_rows(context)
    if request.method == "GET":
        query = request.query_params.get("q", "").strip()
        if query:
            rows = rows.filter(
                Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
                | Q(personnel_code__icontains=query) | Q(user__username__icontains=query),
            )
        return Response([_employee_json(item) for item in rows.order_by("user__last_name", "user__first_name")])
    if not (context.has_role("hr") or _admin(context)):
        return _failure("permission_denied", "مدیریت پرونده کارکنان مجاز نیست", 403)
    data = request.data
    if not isinstance(data, dict):
        return _failure("invalid_payload", "بدنه باید یک شیء JSON باشد", 400)
    try:
        employee = hr_operation_employees(context).get(pk=employee_id) if employee_id is not None else None
    except EmployeeProfile.DoesNotExist:
        raise Http404
    allowed = {
        "displayName", "personnelCode", "companyId", "departmentId", "managerId",
        "startDate", "endDate", "email",
    }
    if set(data) - allowed or not {"displayName", "personnelCode", "companyId"}.issubset(data):
        return _failure("invalid_payload", "نام، کد پرسنلی و شرکت الزامی است", 400)
    if employee is not None and "email" in data:
        return _failure("invalid_payload", "برای تغییر ایمیل از فرایند دعوت استفاده کنید", 400)
    invitation_email = None
    if "email" in data:
        try:
            invitation_email = normalize_email(data["email"])
        except InvitationError:
            return _failure("invalid_employee", "نشانی ایمیل معتبر نیست", 400)
    if not isinstance(data["displayName"], str) or not isinstance(data["personnelCode"], str):
        return _failure("invalid_payload", "نام و کد پرسنلی باید متن باشند", 400)
    try:
        company = Company.objects.get(pk=data["companyId"])
        department_id = int(data["departmentId"]) if data.get("departmentId") else None
        if not _admin(context) and not context.has_scope(
            "hr", company_id=company.pk, site_id=None, department_id=department_id, employee_id=None,
        ):
            return _failure("permission_denied", "ثبت در این شرکت یا واحد مجاز نیست", 403)
        department = Department.objects.get(pk=data["departmentId"]) if data.get("departmentId") else None
        manager = (
            hr_operation_employees(context).get(pk=data["managerId"])
            if data.get("managerId") else None
        )
        start = dt.date.fromisoformat(data["startDate"]) if data.get("startDate") else (
            employee.start_date if employee else timezone.localdate()
        )
        end = dt.date.fromisoformat(data["endDate"]) if data.get("endDate") else (
            employee.end_date if employee else None
        )
        display_name = data["displayName"].strip()
        code = data["personnelCode"].strip()
        if not display_name or not code:
            raise ValueError("نام و کد پرسنلی الزامی است")
        created = employee is None
        with transaction.atomic():
            if employee is None:
                username = f"emp-{company.pk}-{code}"
                if User.objects.filter(username=username).exists():
                    return _failure("duplicate_user", "حساب کاربری با این کد وجود دارد", 409)
                user = User(
                    username=username,
                    first_name=display_name,
                    email=invitation_email or "",
                    is_active=False,
                )
                user.set_unusable_password()
                user.save()
                employee = EmployeeProfile(
                    user=user, company=company, personnel_code=code, start_date=start,
                    account_status=EmployeeProfile.ACCOUNT_CREATED,
                )
            else:
                user = employee.user
                user.first_name = display_name
                user.save(update_fields=["first_name"])
                employee.company, employee.personnel_code = company, code
                employee.start_date = start
            employee.department, employee.manager, employee.end_date = department, manager, end
            if department and department.company_id != company.pk:
                raise ValueError("واحد باید متعلق به شرکت انتخاب‌شده باشد")
            if manager and manager.company_id != company.pk:
                raise ValueError("مدیر باید متعلق به شرکت انتخاب‌شده باشد")
            employee.full_clean()
            employee.save()
            synchronize_employment_access(employee=employee, actor=request.user)
    except (Company.DoesNotExist, Department.DoesNotExist, EmployeeProfile.DoesNotExist):
        return _failure("related_object_not_found", "شرکت، واحد یا مدیر پیدا نشد", 404)
    except (ValueError, TypeError, ValidationError) as exc:
        return _failure("invalid_employee", str(exc), 400)
    except IntegrityError:
        return _failure("duplicate_employee", "کد پرسنلی قبلاً در این شرکت ثبت شده است", 409)
    invitation_result = None
    if (
        created
        and invitation_email
        and employee.account_status != EmployeeProfile.ACCOUNT_OFFBOARDED
    ):
        try:
            invitation_result = invite_employee(
                employee_id=employee.pk,
                actor=request.user,
            )
        except InvitationError:
            return _failure("invitation_failed", "دعوت کاربر ایجاد نشد", 500)
        employee.refresh_from_db()
    result = _employee_json(employee)
    if invitation_result:
        result["invitationStatus"] = invitation_result.status
        result["invitationDelivery"] = (
            "sent" if invitation_result.status == "sent" else "unavailable"
        )
        result["invitationMessageFa"] = (
            "دعوت ارسال شد"
            if invitation_result.status == "sent"
            else "دعوت ذخیره شد اما سرویس ایمیل در دسترس نیست"
        )
        if invitation_result.development_url:
            result["developmentActivationUrl"] = invitation_result.development_url
    return Response(result, status=201 if employee_id is None else 200)


def _company_json(item: Company) -> dict:
    return {"id": item.pk, "code": item.code, "name": item.name, "isActive": item.is_active}


def _department_json(item: Department) -> dict:
    return {"id": item.pk, "companyId": item.company_id, "code": item.code, "name": item.name,
            "parentId": item.parent_id}


@api_view(["GET", "POST", "PATCH"])
def companies(request, company_id: int | None = None):
    context = _context(request)
    if request.method == "GET":
        if _admin(context):
            rows = Company.objects.all()
        else:
            rows = Company.objects.filter(pk__in=_employee_rows(context).values("company_id"))
        return Response([_company_json(item) for item in rows.order_by("name")])
    if not _admin(context):
        return _failure("permission_denied", "مدیریت شرکت‌ها فقط برای مدیر سامانه مجاز است", 403)
    data = request.data
    if not isinstance(data, dict) or set(data) - {"code", "name", "isActive"} or not {"code", "name"} <= set(data):
        return _failure("invalid_payload", "کد و نام شرکت الزامی است", 400)
    if (not isinstance(data["code"], str) or not isinstance(data["name"], str)
            or ("isActive" in data and not isinstance(data["isActive"], bool))):
        return _failure("invalid_payload", "کد و نام باید متن و وضعیت باید بولی باشد", 400)
    item = Company.objects.filter(pk=company_id).first() if company_id else Company()
    if item is None:
        raise Http404
    item.code, item.name = data["code"].strip(), data["name"].strip()
    if "isActive" in data:
        item.is_active = data["isActive"]
    try:
        item.full_clean()
        item.save()
    except (ValidationError, IntegrityError):
        return _failure("invalid_company", "اطلاعات شرکت معتبر نیست", 400)
    return Response(_company_json(item), status=201 if company_id is None else 200)


@api_view(["GET", "POST", "PATCH"])
def departments(request, department_id: int | None = None):
    context = _context(request)
    if request.method == "GET":
        rows = Department.objects.all() if _admin(context) else Department.objects.filter(
            company_id__in=_employee_rows(context).values("company_id"),
        )
        return Response([_department_json(item) for item in rows.order_by("company_id", "name")])
    if not _admin(context):
        return _failure("permission_denied", "مدیریت واحدها فقط برای مدیر سامانه مجاز است", 403)
    data = request.data
    if not isinstance(data, dict) or set(data) - {"code", "name", "companyId", "parentId"} or not {
        "code", "name", "companyId",
    } <= set(data):
        return _failure("invalid_payload", "کد، نام و شرکت الزامی است", 400)
    if not isinstance(data["code"], str) or not isinstance(data["name"], str):
        return _failure("invalid_payload", "کد و نام باید متن باشند", 400)
    item = Department.objects.filter(pk=department_id).first() if department_id else Department()
    if item is None:
        raise Http404
    try:
        item.company = Company.objects.get(pk=data["companyId"])
        item.code, item.name = data["code"].strip(), data["name"].strip()
        item.parent = Department.objects.get(pk=data["parentId"]) if data.get("parentId") else None
        item.full_clean()
        item.save()
    except (Company.DoesNotExist, Department.DoesNotExist):
        return _failure("related_object_not_found", "شرکت یا واحد والد پیدا نشد", 404)
    except (ValidationError, IntegrityError):
        return _failure("invalid_department", "اطلاعات واحد معتبر نیست", 400)
    return Response(_department_json(item), status=201 if department_id is None else 200)


@api_view(["GET", "POST"])
def settings_api(request):
    context = _context(request)
    if not _admin(context):
        return _failure("permission_denied", "تنظیمات فقط برای مدیر سامانه مجاز است", 403)
    definitions = settings_schema.DEFS
    if request.method == "GET":
        values = admin_services.load_settings()
        return Response([{
            "key": key, "value": settings_schema.to_storable(values[key]),
            "default": settings_schema.to_storable(item.default),
            "labelFa": item.label_fa, "group": item.group,
        } for key, item in definitions.items()])
    data = request.data
    if (not isinstance(data, dict) or set(data) != {"key", "value", "reason"}
            or not isinstance(data["key"], str) or not isinstance(data["reason"], str)):
        return _failure("invalid_payload", "کلید، مقدار و دلیل الزامی است", 400)
    try:
        admin_services.set_setting(
            user=request.user, key=data["key"], value=data["value"], reason=data["reason"],
        )
    except settings_schema.SettingError as exc:
        return _failure("invalid_setting", str(exc), 400)
    values = admin_services.load_settings()
    item = definitions[data["key"]]
    return Response({
        "key": data["key"], "value": settings_schema.to_storable(values[data["key"]]),
        "default": settings_schema.to_storable(item.default),
        "labelFa": item.label_fa, "group": item.group,
    })


@api_view(["GET"])
def audit_events(request):
    context = _context(request)
    is_admin = _admin(context)
    if is_admin:
        rows = AuditEvent.objects.all()
    elif context.has_role("hr"):
        request_ids = scoped_hr_leave_requests(context).values("pk")
        rows = AuditEvent.objects.filter(entity="LeaveRequest", entity_id__in=request_ids)
    else:
        return _failure("permission_denied", "مشاهده حسابرسی مجاز نیست", 403)
    rows = rows.select_related("actor").order_by("-created_at", "-pk")[:500]
    return Response([{
        "id": item.pk, "actorName": (
            item.actor.get_full_name() or item.actor.get_username() if item.actor_id else None
        ), "action": item.action, "entity": item.entity, "entityId": item.entity_id,
        "reason": item.reason, "result": item.result, "createdAt": item.created_at.isoformat(),
        "before": item.before if is_admin else None,
        "after": item.after if is_admin else None,
        "correlationId": item.correlation_id if is_admin else None,
    } for item in rows])


@api_view(["GET"])
def jobs(request):
    if not _admin(_context(request)):
        return _failure("permission_denied", "مشاهده Jobها فقط برای مدیر سامانه مجاز است", 403)
    return Response([])


@api_view(["GET"])
def client_policy(request):
    context = _context(request)
    if not context.employee:
        return _failure("employee_profile_required", "پرونده کارمندی برای دریافت سیاست لازم است", 403)
    today = timezone.localdate()
    from .calendar_services import _patterns_for

    pattern = next(iter(_patterns_for(context.employee, today, today)), None)
    return Response({
        "hourlyLeaveEnabled": False,
        "workdayStart": pattern.start_time.strftime("%H:%M") if pattern else "",
        "workdayEnd": pattern.end_time.strftime("%H:%M") if pattern else "",
        "hourlyAllowOutsideWorkHours": False,
        "hourlyAllowOnHoliday": False,
        "hourlyMaxMinutesPerRequest": 0,
        "workdayMinutes": pattern.daily_work_minutes if pattern else 0,
        "autoCancelEnabled": False,
        "autoCancelDays": None,
        "timezoneLabel": timezone.get_current_timezone_name(),
    })


def _visible_events(context):
    if context.has_role("admin"):
        return LeaveRequestEvent.objects.none()
    request_scope = Q()
    if context.employee_id:
        request_scope |= (
            Q(employee_id=context.employee_id) | Q(manager_snapshot_id=context.employee_id)
        )
    if context.has_role("hr"):
        request_scope |= Q(pk__in=scoped_hr_leave_requests(context).values("pk"))
    if not request_scope:
        return LeaveRequestEvent.objects.none()
    return LeaveRequestEvent.objects.filter(
        request_id__in=LeaveRequest.objects.filter(request_scope).values("pk"),
    ).exclude(actor_id=context.user.pk)


def _notification_json(event: LeaveRequestEvent, read: bool) -> dict:
    title_by_event = {
        "submit": "درخواست مرخصی جدید",
        "approve": "درخواست مرخصی تأیید شد",
        "reject": "درخواست مرخصی رد شد",
        "cancel": "درخواست مرخصی لغو شد",
        "request_withdraw": "درخواست لغو مرخصی ثبت شد",
        "approve_withdraw": "لغو مرخصی تأیید شد",
        "reject_withdraw": "لغو مرخصی رد شد",
    }
    return {
        "id": event.pk,
        "title": title_by_event.get(event.event, "وضعیت درخواست تغییر کرد"),
        "body": f"وضعیت درخواست {event.request_id} به {event.to_status} تغییر کرد.",
        "read": read, "createdAt": event.created_at.isoformat(),
        "requestId": event.request_id, "kind": event.event, "category": "leave",
    }


@api_view(["GET"])
def notifications(request):
    context = _context(request)
    rows = _visible_events(context).select_related("request__leave_type").order_by("-created_at", "-pk")[:200]
    read_ids = set(NotificationRead.objects.filter(
        user=request.user, event_id__in=[row.pk for row in rows],
    ).values_list("event_id", flat=True))
    return Response([_notification_json(row, row.pk in read_ids) for row in rows])


@api_view(["POST"])
def notification_read(request, notification_id: int):
    context = _context(request)
    event = _visible_events(context).filter(pk=notification_id).first()
    if event is None:
        raise Http404
    NotificationRead.objects.get_or_create(user=request.user, event=event)
    return Response(status=204)


@rate_limited("expensive_operation")
@api_view(["GET"])
def coverage(request):
    context = _context(request)
    if not (context.has_role("manager") or context.has_role("hr") or _admin(context)):
        return _failure("permission_denied", "گزارش پوشش فقط برای مدیر یا HR مجاز است", 403)
    try:
        start = dt.date.fromisoformat(request.query_params["from"])
        end = dt.date.fromisoformat(request.query_params["to"])
        if start > end or (end - start).days > 92:
            raise ValueError
    except (KeyError, ValueError):
        return _failure("invalid_range", "بازه تاریخ معتبر و حداکثر ۹۳ روز باشد", 400)
    if context.has_role("hr"):
        eligible = scoped_hr_leave_requests(context)
        employee_rows = hr_operation_employees(context)
    elif context.employee_id:
        eligible = LeaveRequest.objects.filter(manager_snapshot_id=context.employee_id)
        employee_rows = EmployeeProfile.objects.filter(manager_id=context.employee_id)
    else:
        return _failure("permission_denied", "دامنه گزارش پوشش مشخص نیست", 403)
    approved = eligible.filter(status="APPROVED", start_date__lte=end, end_date__gte=start)
    if not context.has_role("hr"):
        approved = approved.filter(leave_type__confidential=False)
    department_ids = employee_rows.values_list("department_id", flat=True)
    departments = Department.objects.filter(pk__in=department_ids).distinct()
    result = []
    for day in (start + dt.timedelta(days=n) for n in range((end - start).days + 1)):
        for department in departments:
            away = approved.filter(
                employee__department=department, start_date__lte=day, end_date__gte=day,
            ).values("employee_id").distinct().count()
            headcount = employee_rows.filter(department=department, end_date__isnull=True).count()
            result.append({
                "date": day.isoformat(), "departmentName": department.name,
                "awayCount": away, "headcount": headcount,
            })
    return Response(result)


@rate_limited("expensive_operation")
@api_view(["GET"])
def reports(request, kind: str):
    context = _context(request)
    if not (context.has_role("hr") or context.has_role("exec")):
        return _failure("permission_denied", "مشاهده گزارش‌ها مجاز نیست", 403)
    if kind not in {"absences", "balances", "trends", "process-health", "bradford"}:
        return _failure("unknown_report", "نوع گزارش شناخته‌شده نیست", 404)
    if context.has_role("hr"):
        rows = scoped_hr_leave_requests(context)
        people = EmployeeProfile.objects.filter(pk__in=rows.values("employee_id"))
    else:
        employee_scope = Q()
        for assignment in RoleAssignment.objects.filter(user=request.user, role="exec", is_active=True):
            if assignment.scope == RoleAssignment.SCOPE_COMPANY:
                employee_scope |= Q(company_id=assignment.company_id)
            elif assignment.scope == RoleAssignment.SCOPE_SITE:
                employee_scope |= Q(company_id=assignment.company_id, site_id=assignment.site_id)
            elif assignment.scope == RoleAssignment.SCOPE_DEPARTMENT:
                employee_scope |= Q(company_id=assignment.company_id, department_id=assignment.department_id)
        people = EmployeeProfile.objects.filter(employee_scope, is_employee=True)
        rows = LeaveRequest.objects.filter(employee_id__in=people.values("pk"))
    try:
        min_size = settings_schema.resolve({
            setting.key: setting.value for setting in SystemSetting.objects.all()
        })["privacy.min_group_size"]
    except settings_schema.SettingError as exc:
        return _failure("invalid_settings", str(exc), 409)
    report_rows = rows if context.has_role("hr") else rows.filter(leave_type__confidential=False)
    approved = report_rows.filter(status="APPROVED")
    if kind == "absences":
        categories = approved.values("leave_type__label_fa").annotate(
            total=Count("pk"), people=Count("employee_id", distinct=True),
        )
        series = [
            {"label": item["leave_type__label_fa"], "value": item["total"]}
            for item in categories if item["people"] >= min_size
        ]
    elif kind == "balances":
        entitlements = LeaveEntitlement.objects.filter(employee_id__in=people.values("pk"))
        if not context.has_role("hr"):
            entitlements = entitlements.filter(leave_type__confidential=False)
        count = entitlements.values(
            "employee_id",
        ).distinct().count()
        series = [{"label": "دارای سهمیه", "value": count}] if count >= min_size else []
    elif kind == "trends":
        categories = approved.values("start_date__month").annotate(
            total=Count("pk"), people=Count("employee_id", distinct=True),
        ).order_by("start_date__month")
        series = [
            {"label": str(item["start_date__month"]), "value": item["total"]}
            for item in categories if item["people"] >= min_size
        ]
    elif kind == "process-health":
        categories = report_rows.values("status").annotate(
            total=Count("pk"), people=Count("employee_id", distinct=True),
        ).order_by("status")
        series = [
            {"label": item["status"], "value": item["total"]}
            for item in categories if item["people"] >= min_size
        ]
    else:
        return Response({
            "title": kind, "series": [],
            "note": "تحلیل Bradford در صفحه اختصاصی منابع انسانی و بر پایه قرارداد و تقویم کارکنان محاسبه می‌شود.",
        })
    total_people = people.count()
    if total_people < min_size:
        return Response({"title": kind, "note": "برای رعایت حداقل گروه، داده این گزارش نمایش داده نمی‌شود.", "series": []})
    return Response({"title": kind, "series": series})


@api_view(["GET", "POST"])
def bradford_notes(request):
    context = _context(request)
    if not (context.has_role("hr") or _admin(context)):
        return _failure("permission_denied", "دسترسی یادداشت Bradford مجاز نیست", 403)
    employee_rows = hr_operation_employees(context)
    if request.method == "GET":
        notes = BradfordNote.objects.select_related("employee__user", "updated_by").filter(
            employee_id__in=employee_rows.values("pk"),
        ).order_by("employee_id")
        return Response([{
            "employeeId": item.employee_id, "body": item.body,
            "updatedAt": item.updated_at.isoformat(),
            "authorName": item.updated_by.get_full_name() or item.updated_by.get_username(),
        } for item in notes])
    data = request.data
    if not isinstance(data, dict) or set(data) != {"employeeId", "body"}:
        return _failure("invalid_payload", "شناسه کارمند و متن یادداشت الزامی است", 400)
    try:
        employee = employee_rows.get(pk=data["employeeId"])
    except (EmployeeProfile.DoesNotExist, ValueError, TypeError):
        raise Http404
    body = data["body"]
    if not isinstance(body, str) or not body.strip() or len(body) > 4000:
        return _failure("invalid_note", "متن یادداشت الزامی و حداکثر ۴۰۰۰ نویسه است", 400)
    note, _ = BradfordNote.objects.update_or_create(
        employee=employee, defaults={"body": body.strip(), "updated_by": request.user},
    )
    return Response({
        "employeeId": note.employee_id, "body": note.body,
        "updatedAt": note.updated_at.isoformat(),
        "authorName": request.user.get_full_name() or request.user.get_username(),
    })


def _contract_json(item: ContractPeriod) -> dict:
    return {
        "id": item.pk, "employeeId": item.employee_id,
        "start": item.start_date.isoformat(), "end": item.end_date.isoformat() if item.end_date else None,
        "workDays": item.work_days, "contractPercent": float(item.contract_percent),
    }


@api_view(["GET", "POST"])
def contracts(request, employee_id: int):
    context = _context(request)
    if not (context.has_role("hr") or _admin(context)):
        return _failure("permission_denied", "مشاهده یا تغییر قرارداد مجاز نیست", 403)
    employee = hr_operation_employees(context).filter(pk=employee_id).first()
    if employee is None:
        raise Http404
    if request.method == "GET":
        rows = ContractPeriod.objects.filter(employee=employee)
        return Response([_contract_json(item) for item in rows])
    data = request.data
    if not isinstance(data, dict) or set(data) != {"employeeId", "start", "end", "workDays", "contractPercent"}:
        return _failure("invalid_payload", "اطلاعات قرارداد معتبر نیست", 400)
    try:
        if int(data["employeeId"]) != employee.pk:
            raise ValueError
        start = dt.date.fromisoformat(data["start"])
        end = dt.date.fromisoformat(data["end"]) if data["end"] else None
        days = data["workDays"]
        percent = Decimal(str(data["contractPercent"]))
        if (not isinstance(days, list) or not days or
                any(type(day) is not int or day < 0 or day > 6 for day in days) or
                len(set(days)) != len(days) or not percent.is_finite() or
                percent <= 0 or percent > 100 or (end and start > end)):
            raise ValueError
        overlaps = ContractPeriod.objects.filter(
            employee=employee, start_date__lte=end or dt.date.max,
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=start)).exists()
        if overlaps:
            return _failure("contract_period_conflict", "بازه قرارداد با قرارداد ثبت‌شده هم‌پوشانی دارد", 409)
        item = ContractPeriod.objects.create(
            employee=employee, start_date=start, end_date=end,
            work_days=days, contract_percent=percent, created_by=request.user,
        )
    except (ValueError, TypeError, InvalidOperation):
        return _failure("invalid_contract", "بازه، روزهای کاری یا درصد قرارداد معتبر نیست", 400)
    return Response(_contract_json(item), status=201)


@rate_limited("file_upload")
@api_view(["GET", "POST"])
def request_attachments(request, request_id: int):
    from .workflow_views import _comment_allowed, _visible_request

    context = _context(request)
    row = _visible_request(request_id, context)
    if not _comment_allowed(context, row):
        return _failure("permission_denied", "دسترسی به پیوست این درخواست مجاز نیست", 403)
    if request.method == "GET":
        return Response([{
            "id": attachment.pk,
            "fileName": attachment.file_name,
            "sizeLabel": f"{max(1, round(attachment.file_size / 1024))} KB",
            "createdAt": attachment.created_at.isoformat(),
            "downloadUrl": f"/api/v1/leave-requests/{request_id}/attachments/{attachment.pk}/",
        } for attachment in row.attachments.all()])

    upload = request.FILES.get("file")
    if upload is None:
        return _failure("invalid_attachment", "فایل پیوست الزامی است", 400)
    if upload.size == 0 or upload.size > 10 * 1024 * 1024:
        return _failure("invalid_attachment", "حجم فایل باید بین ۱ بایت و ۱۰ مگابایت باشد", 400)
    file_name = upload.name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    accepted = {
        "pdf": ("application/pdf", b"%PDF-"),
        "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
        "jpg": ("image/jpeg", b"\xff\xd8\xff"),
        "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    }
    if extension not in accepted or len(file_name) > 255:
        return _failure("invalid_attachment", "فقط فایل PDF، PNG یا JPEG مجاز است", 400)
    content_type, signature = accepted[extension]
    if upload.content_type != content_type or upload.read(len(signature)) != signature:
        return _failure("invalid_attachment", "نوع یا محتوای فایل با پسوند آن سازگار نیست", 400)
    upload.seek(0)
    attachment = LeaveRequestAttachment.objects.create(
        request=row, file=upload, file_name=file_name, content_type=content_type,
        file_size=upload.size, uploaded_by=request.user,
    )
    return Response({
        "id": attachment.pk, "fileName": attachment.file_name,
        "sizeLabel": f"{max(1, round(attachment.file_size / 1024))} KB",
        "createdAt": attachment.created_at.isoformat(),
        "downloadUrl": f"/api/v1/leave-requests/{request_id}/attachments/{attachment.pk}/",
    }, status=201)


@rate_limited("file_access")
@api_view(["GET"])
def request_attachment_download(request, request_id: int, attachment_id: int):
    from .workflow_views import _comment_allowed, _visible_request

    context = _context(request)
    row = _visible_request(request_id, context)
    if not _comment_allowed(context, row):
        return _failure("permission_denied", "دسترسی به پیوست این درخواست مجاز نیست", 403)
    attachment = row.attachments.filter(pk=attachment_id).first()
    if attachment is None:
        raise Http404
    response = FileResponse(
        attachment.file.open("rb"), as_attachment=True,
        filename=attachment.file_name, content_type=attachment.content_type,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@api_view(["POST"])
def hr_absence(request):
    from .services import run_idempotent, submit_request
    from .workflow_views import (
        _payload, _request_body, _submit_permission, _workflow_error,
    )

    context = _context(request)
    data = request.data
    allowed = {"employeeId", "leaveTypeKey", "start", "end", "workingDays", "reason", "replacementId"}
    if not context.has_role("hr"):
        return _failure("permission_denied", "ثبت غیبت فقط برای HR مجاز است", 403)
    if not isinstance(data, dict) or set(data) - allowed:
        return _failure("invalid_payload", "اطلاعات غیبت معتبر نیست", 400)
    try:
        employee = hr_operation_employees(context).get(pk=data["employeeId"])
        if not _submit_permission(context, employee):
            return _failure("permission_denied", "ثبت غیبت برای این کارمند مجاز نیست", 403)
        leave_type = LeaveType.objects.get(key=data["leaveTypeKey"])
        fields = _request_body({key: data[key] for key in allowed - {"employeeId"} if key in data})
        replacement = (
            hr_operation_employees(context).filter(pk=fields["replacement_id"]).first()
            if fields["replacement_id"] is not None else None
        )
        if fields["replacement_id"] is not None and replacement is None:
            raise ValueError("جانشین معتبر نیست")

        def create_absence():
            return submit_request(
                user=request.user, employee=employee, leave_type=leave_type,
                start=fields["start"], end=fields["end"], reason=fields["reason"],
                replacement=replacement, working_days=fields["working_days"],
            )

        with transaction.atomic():
            result = run_idempotent(
                user=request.user,
                key=request.headers.get("Idempotency-Key", ""),
                operation="hr.absence",
                payload={"employeeId": employee.pk, "leaveTypeKey": leave_type.key,
                         "start": fields["start"], "end": fields["end"], "reason": fields["reason"],
                         "workingDays": fields["working_days"],
                         "replacementId": fields["replacement_id"]},
                model=LeaveRequest, callback=create_absence,
            )
        return Response(_payload(result, context), status=201)
    except (EmployeeProfile.DoesNotExist, LeaveType.DoesNotExist):
        raise Http404
    except Exception as exc:
        return _workflow_error(exc)
