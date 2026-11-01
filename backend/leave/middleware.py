from __future__ import annotations

import re
from contextvars import ContextVar
from uuid import uuid4


_CORRELATION_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_audit_context: ContextVar[dict | None] = ContextVar("leave_audit_context", default=None)


def current_audit_context() -> dict | None:
    return _audit_context.get()


class AuditContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied if _CORRELATION_PATTERN.fullmatch(supplied) else str(uuid4())
        request.correlation_id = correlation_id
        source = f"{request.method} {request.path_info}"[:128]
        token = _audit_context.set({"correlation_id": correlation_id, "source": source})
        try:
            response = self.get_response(request)
            response["X-Correlation-ID"] = correlation_id
            return response
        finally:
            _audit_context.reset(token)
