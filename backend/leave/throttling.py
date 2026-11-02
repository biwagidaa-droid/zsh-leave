import hashlib
import ipaddress
import logging

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.throttling import (
    AnonRateThrottle,
    ScopedRateThrottle,
    SimpleRateThrottle,
    UserRateThrottle,
)

logger = logging.getLogger("leave.security")


def trusted_client_ip(request):
    remote_addr = request.META.get("REMOTE_ADDR", "")
    try:
        remote_ip = ipaddress.ip_address(remote_addr)
    except ValueError:
        return "unknown"

    trusted_proxies = settings.ZSH_TRUSTED_PROXY_NETWORKS
    if not any(remote_ip in network for network in trusted_proxies):
        return remote_ip.compressed

    forwarded_for = request.headers.get("X-Forwarded-For")
    if not forwarded_for:
        return remote_ip.compressed

    try:
        forwarded_ips = [
            ipaddress.ip_address(value.strip())
            for value in forwarded_for.split(",")
        ]
    except ValueError:
        return remote_ip.compressed
    if not forwarded_ips:
        return remote_ip.compressed

    for client_ip in reversed([*forwarded_ips, remote_ip]):
        if not any(client_ip in network for network in trusted_proxies):
            return client_ip.compressed
    return remote_ip.compressed


def _cache_ident(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AbuseLoggingThrottleMixin:
    def throttle_failure(self):
        logger.warning(
            "event=rate_limit_exceeded throttle_scope=%s",
            self.scope,
            extra={"event": "rate_limit_exceeded", "throttle_scope": self.scope},
        )
        return super().throttle_failure()


class TrustedClientThrottleMixin:
    def get_ident(self, request):
        return trusted_client_ip(request)


class AnonymousClientThrottle(AbuseLoggingThrottleMixin, TrustedClientThrottleMixin, AnonRateThrottle):
    pass


class AuthenticatedUserThrottle(AbuseLoggingThrottleMixin, UserRateThrottle):
    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class AuthenticatedClientThrottle(
    AbuseLoggingThrottleMixin,
    TrustedClientThrottleMixin,
    SimpleRateThrottle,
):
    scope = "authenticated_client"

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": _cache_ident(self.get_ident(request)),
        }


class ScopedClientThrottle(
    AbuseLoggingThrottleMixin,
    TrustedClientThrottleMixin,
    ScopedRateThrottle,
):
    def get_cache_key(self, request, view):
        if not self.scope:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": _cache_ident(self.get_ident(request)),
        }


class ScopedUserThrottle(AbuseLoggingThrottleMixin, ScopedRateThrottle):
    def get_cache_key(self, request, view):
        if not self.scope or not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": request.user.pk,
        }


class LoginAccountThrottle(AbuseLoggingThrottleMixin, ScopedRateThrottle):
    def allow_request(self, request, view):
        if getattr(view, self.scope_attr, None) != "auth_login":
            return True

        self.scope = "auth_login_account"
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return SimpleRateThrottle.allow_request(self, request, view)

    def get_cache_key(self, request, view):
        username = request.data.get("username") if isinstance(request.data, dict) else None
        if not isinstance(username, str) or not username.strip():
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": _cache_ident(username.strip().casefold()),
        }


def rate_limited(scope):
    def decorate(view):
        view.cls.throttle_scope = scope
        return view

    return decorate


def rate_limit_exception_handler(exc, context):
    from rest_framework.views import exception_handler

    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, Throttled):
        wait = exc.wait
        response.data = {
            "code": "rate_limited",
            "detail": "Request was throttled.",
            "retry_after": int(wait) if wait is not None else None,
        }
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return response
