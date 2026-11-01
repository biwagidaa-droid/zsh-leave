import logging

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth import password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError
from django.middleware.csrf import CsrfViewMiddleware, get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .authorization import authorization_context
from .invitation_services import account_access_allowed
from .models import AuditEvent, EmployeeProfile

logger = logging.getLogger("leave.auth")


class LoginRateThrottle(AnonRateThrottle):
    scope = "auth_login"


def _record_auth_event(action, entity_id, actor=None, result="ok"):
    AuditEvent.objects.create(
        actor=actor,
        origin="auth",
        action=action,
        entity="User",
        entity_id=str(entity_id)[:64],
        before=None,
        after=None,
        reason="",
        result=result,
    )


def _csrf_error(request):
    middleware = CsrfViewMiddleware(lambda _request: None)
    reason = middleware.process_view(request, lambda _request: None, (), {})
    if reason is not None:
        return Response(
            {
                "code": "csrf_failed",
                "message_fa": "درخواست معتبر نیست؛ صفحه را تازه‌سازی کنید و دوباره تلاش کنید",
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


def _user_payload(user):
    authorization = authorization_context(user)
    profile = (
        EmployeeProfile.objects.select_related(
            "company", "department", "manager__user"
        )
        .filter(user=user)
        .first()
    )
    roles = [
        role for role in ("admin", "hr", "exec", "employee", "manager")
        if authorization.has_role(role)
    ]

    display_name = user.get_full_name().strip() or user.username
    manager_name = None
    if profile and profile.manager:
        manager_name = profile.manager.user.get_full_name().strip() or profile.manager.user.username

    return {
        "id": user.pk,
        "username": user.get_username(),
        "displayName": display_name,
        "email": user.email,
        "roles": roles,
        "employeeId": profile.pk if profile else None,
        "companyId": profile.company_id if profile else None,
        "companyName": profile.company.name if profile else "",
        "departmentName": profile.department.name if profile and profile.department else "",
        "personnelCode": profile.personnel_code if profile else "",
        "managerName": manager_name,
        "isEmployee": bool(profile and profile.is_employee),
    }


def _invalid_request(fields):
    return Response(
        {
            "code": "invalid_request",
            "message_fa": "اطلاعات واردشده معتبر نیست",
            "fields": fields,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    csrf_response = _csrf_error(request)
    if csrf_response is not None:
        return csrf_response

    data = request.data
    if not isinstance(data, dict):
        return _invalid_request({"request": "بدنه درخواست نامعتبر است"})
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username or not isinstance(password, str) or not password:
        return _invalid_request({"credentials": "نام کاربری و رمز عبور الزامی است"})

    user = authenticate(request=request, username=username, password=password)
    if user is None or not account_access_allowed(user):
        _record_auth_event("auth.login.failed", username, result="failed")
        logger.warning("Authentication failed")
        return Response(
            {
                "code": "invalid_credentials",
                "message_fa": "نام کاربری یا رمز عبور نادرست است",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    auth_login(request, user)
    request.session.set_expiry(8 * 60 * 60)
    _record_auth_event("auth.login.succeeded", user.pk, actor=user)
    get_token(request)
    return Response(_user_payload(user), status=status.HTTP_200_OK)


@api_view(["POST"])
def logout(request):
    csrf_response = _csrf_error(request)
    if csrf_response is not None:
        return csrf_response
    _record_auth_event("auth.logout", request.user.pk, actor=request.user)
    auth_logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([AllowAny])
def current_user(request):
    get_token(request)
    if not request.user.is_authenticated:
        return Response(
            {
                "code": "unauthenticated",
                "message_fa": "نشست شما معتبر نیست؛ دوباره وارد شوید",
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response(_user_payload(request.user))


@api_view(["POST"])
def change_password(request):
    csrf_response = _csrf_error(request)
    if csrf_response is not None:
        return csrf_response

    data = request.data
    if not isinstance(data, dict):
        return _invalid_request({"request": "بدنه درخواست نامعتبر است"})
    current, next_password = data.get("current"), data.get("next")
    if not isinstance(current, str) or not isinstance(next_password, str) or not current or not next_password:
        return _invalid_request({"password": "رمز فعلی و رمز جدید الزامی است"})

    user = request.user
    if not user.check_password(current):
        return Response(
            {
                "code": "invalid_current_password",
                "message_fa": "رمز عبور فعلی نادرست است",
                "fields": {"current": "رمز عبور فعلی نادرست است"},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        password_validation.validate_password(next_password, user)
    except ValidationError as exc:
        return _invalid_request({"next": " ".join(exc.messages)})

    user.set_password(next_password)
    user.save(update_fields=["password"])
    update_session_auth_hash(request, user)
    _record_auth_event("auth.password.changed", user.pk, actor=user)
    return Response(status=status.HTTP_204_NO_CONTENT)
