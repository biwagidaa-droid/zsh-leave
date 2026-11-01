# API Contract

## 1. Scope and Status
This contract reflects the current state of the actual backend and frontend integration and is intentionally limited to the implemented or planned public API surface. The mission does not implement full business workflows.

## 2. Base URL
- `/api/v1/`

## 3. API Inventory

### `GET /api/v1/health/`
- Status: Implemented
- Permission: AllowAny
- Response: JSON status object
- Success body example:
  ```json
  {
    "status": "ok",
    "service": "zsh-leave",
    "timestamp": "2026-11-01T00:00:00+00:00"
  }
  ```
- Error responses: none beyond server-level failures

### `GET /api/v1/ready/`
- Status: Implemented
- Permission: AllowAny
- Response: JSON readiness object with database check
- Success body example:
  ```json
  {
    "status": "ready",
    "checks": [
      {"name": "database", "ok": true, "message": "database reachable"}
    ],
    "timestamp": "2026-11-01T00:00:00+00:00"
  }
  ```
- Failure status: HTTP 503 with a non-sensitive message if infra dependencies are unavailable

### `GET /api/v1/calendar/convert-date/`
- Status: Implemented (Phase 06 foundation)
- Permission: AllowAny; stateless conversion with no organization data
- Query parameters:
  - `calendar`: `jalali` or `gregorian`
  - `date`: `YYYY/MM/DD` for Jalali (Persian digits accepted), or `YYYY-MM-DD` for Gregorian
- Success response:
  ```json
  {
    "gregorian": "2025-03-21",
    "jalali": "1404/01/01"
  }
  ```
- Invalid calendar/date: HTTP 400 with `code` and `message_fa`
- Jalali dates outside the supported conversion range are rejected; they are not silently approximated.

### Schema endpoints
- `GET /api/v1/schema/` — Implemented via drf-spectacular
- `GET /api/v1/docs/` — Implemented via Swagger UI

## 4. Planned but Unimplemented
- leave request list/create/update/actions
- entitlement endpoints
- holiday management endpoints
- organization calendar, work-pattern, and timeline endpoints
- versioned leave-policy endpoints
- report generation endpoints
- admin setting endpoints
- auth session and permission endpoints

## 5. Notes
- Pagination, filtering, and idempotency are not yet enforced at the general API layer because the higher-level business endpoints are not yet implemented.
- The contract is intentionally conservative and aligned with the current frontend surface rather than introducing unsupported domain commitments.
