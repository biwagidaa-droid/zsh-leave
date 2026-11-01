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

### Phase 06 operational calendar APIs

All data-bearing endpoints require the configured authenticated session. Management APIs are currently restricted to Django superusers; this is a temporary least-privilege boundary, not the final HR/organization RBAC model.

| Method | Endpoint | Contract |
|---|---|---|
| GET | `/api/v1/calendar/events/?from=YYYY-MM-DD&to=YYYY-MM-DD&scope=me\|team\|org` | Calendar events; team is limited to direct reports in the same company; `org` requires Django group `HR` and an employee profile and is limited to that profile's company. Cross-company HR scope is not implemented. |
| GET | `/api/v1/calendar/holidays/?from=YYYY-MM-DD&to=YYYY-MM-DD` | Active range holidays applicable to the authenticated employee's national, organization, company, and site scopes. |
| GET | `/api/v1/working-days/estimate?employee={id}&start=YYYY-MM-DD&end=YYYY-MM-DD` | Backend day-count estimate; an employee can query only their own profile unless superuser. |
| GET/POST | `/api/v1/calendar/work-patterns/` | Read effective patterns for own profile; create a validated pattern as superuser. |
| GET/POST | `/api/v1/calendar/policies/` | Read effective policy for own profile (optional `date`); create immutable policy version as superuser. |
| GET/POST | `/api/v1/calendar/holidays/manage/` | List or create range-based holidays; superuser-only. |
| PATCH/DELETE | `/api/v1/calendar/holidays/manage/{id}/` | Edit or logically deactivate; deactivation requires a reason and writes history/audit. |
| GET | `/api/v1/calendar/holidays/manage/{id}/history/` | Holiday history; superuser-only. |
| GET | `/api/v1/admin/calendar/work-patterns/` | Work-pattern history; superuser-only. |
| GET | `/api/v1/admin/calendar/policies/` | Policy-version history; superuser-only. |

Dates in these contracts are Gregorian ISO dates. Jalali entry/display belongs to the presentation layer; backend remains authoritative for validation and workday calculations. Workday and policy configuration is required: missing configuration returns a conflict rather than silently using a guessed default.

The legacy `/api/v1/holidays/` API remains available for one-day Jalali `PublicHoliday` entries and uses the same superuser-only write boundary. Its DELETE operation is logical deactivation and requires a reason.

### Schema endpoints
- `GET /api/v1/schema/` — Implemented via drf-spectacular
- `GET /api/v1/docs/` — Implemented via Swagger UI

## 4. Planned but Unimplemented
- HR role and company/site/department scoped permission management
- Frontend management screens for range holidays, work patterns, and policy versions
- backend-authoritative hourly leave calculations tied to work patterns and holidays
- leave-year configuration, rollover, expiry, and their ledger operations
- full employee/HR workflow endpoints
- report generation endpoints
- admin setting endpoints
- authentication/session lifecycle APIs

## 5. Notes
- Pagination, filtering, and idempotency are not yet enforced at the general API layer because the higher-level business endpoints are not yet implemented.
- The contract is intentionally conservative and aligned with the current frontend surface rather than introducing unsupported domain commitments.
