# API Contract

## 1. Scope and Status
This contract reflects the current state of the actual backend and frontend integration and is intentionally limited to the implemented or planned public API surface.

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

### Authentication and account lifecycle

These same-origin endpoints use Django session cookies and match the frontend HTTP client paths (no trailing slash).

| Method | Endpoint | Contract |
|---|---|---|
| POST | `/api/v1/auth/login` | Accepts `{ "username": "...", "password": "..." }`; returns the authenticated frontend `User` shape. Invalid credentials and inactive accounts share a generic 401 response. Login is CSRF-protected and limited to 5 attempts/minute per client IP. |
| POST | `/api/v1/auth/logout` | Requires an authenticated session and CSRF token; invalidates the session and returns 204. |
| GET | `/api/v1/auth/me` | Returns the authenticated frontend `User` shape, or 401 when there is no valid session. Also bootstraps/refreshes the CSRF cookie for the SPA. |
| POST | `/api/v1/auth/password` | Requires an authenticated session and CSRF token; accepts `{ "current": "...", "next": "..." }`, validates the new password, and returns 204. The session remains active with its key rotated. |

Sessions expire after eight hours and are browser-session cookies. Session cookies are HttpOnly and SameSite=Lax; production cookies require HTTPS. Passwords are stored with Argon2, while existing PBKDF2 hashes remain verifiable and upgrade on successful authentication. Employee creation provisions a username with an unusable password; password reset/onboarding is not exposed by this API.

The `roles` and organization fields in the user response are display/route metadata resolved from the backend authorization context. Actual API access is independently enforced server-side and never trusts frontend roles.

### RBAC administration

| Method | Endpoint | Contract |
|---|---|---|
| GET/POST | `/api/v1/admin/role-assignments/` | System-administrator only. Lists active assignments or creates one using `{ "userId", "role", "scope", "companyId?", "siteId?", "departmentId?", "employeeId?" }`. Only HR, admin, and executive roles are assignable; admin must be global, HR must have an explicit supported scope, and executive scopes cannot target one employee. Unknown fields and self-assignment are rejected. |
| DELETE | `/api/v1/admin/role-assignments/{id}/` | System-administrator only. Soft-revokes an assignment and writes an audit event. Self-revocation is rejected; unknown/inactive IDs return 404. |

Grants and revocations are audited and take effect on the next request. Existing HR/Executive Django groups are migrated only when an employee/company mapping exists; group membership alone is not authorization.

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

All data-bearing endpoints require the configured authenticated session. Every endpoint below applies server-side role and organization-scope checks; frontend route guards are not security controls.

| Method | Endpoint | Contract |
|---|---|---|
| GET | `/api/v1/calendar/events/?from=YYYY-MM-DD&to=YYYY-MM-DD&scope=me\|team\|org` | Calendar events; `me` is personal, `team` uses the request manager snapshot, and `org` requires active HR assignment(s) and returns only their company/site/department/employee scopes. |
| GET | `/api/v1/calendar/holidays/?from=YYYY-MM-DD&to=YYYY-MM-DD` | Active range holidays applicable to the authenticated employee's national, organization, company, and site scopes. |
| GET | `/api/v1/working-days/estimate?employee={id}&start=YYYY-MM-DD&end=YYYY-MM-DD` | Backend day-count estimate; employees may query themselves, managers their current direct reports, and HR only assigned scope. Other employee IDs return 404. |
| GET/POST | `/api/v1/calendar/work-patterns/` | Read effective patterns for own profile; create a validated pattern with system-configuration permission. |
| GET/POST | `/api/v1/calendar/policies/` | Read effective policy for own profile (optional `date`); create immutable policy version with system-configuration permission. |
| GET/POST | `/api/v1/calendar/holidays/manage/` | List or create range-based holidays; requires system-configuration permission. |
| PATCH/DELETE | `/api/v1/calendar/holidays/manage/{id}/` | Edit or logically deactivate; deactivation requires a reason and writes history/audit. Requires system-configuration permission. |
| GET | `/api/v1/calendar/holidays/manage/{id}/history/` | Holiday history; requires system-configuration permission. |
| GET | `/api/v1/admin/calendar/work-patterns/` | Work-pattern history; requires system-configuration permission. |
| GET | `/api/v1/admin/calendar/policies/` | Policy-version history; requires system-configuration permission. |

Dates in these contracts are Gregorian ISO dates. Jalali entry/display belongs to the presentation layer; backend remains authoritative for validation and workday calculations. Workday and policy configuration is required: missing configuration returns a conflict rather than silently using a guessed default.

### Phase D operational leave workflow

All leave-request endpoints require an authenticated session. Request visibility is limited to the owner, the request's manager snapshot, or HR with matching organization scope; system administrators and executive viewers do not gain individual-record access. Mutations require an `Idempotency-Key` header (1–128 characters). Reusing a key with the same actor, operation, and payload returns the original resource; reusing it for different input returns 409. Workflow state changes and their append-only event/audit records commit atomically.

| Method | Endpoint | Contract |
|---|---|---|
| GET/POST | `/api/v1/leave-requests/` | List scoped requests with `scope=me\|team`, optional `status`, `q`, `page`, and `page_size` (maximum 100), or submit using `employeeId?`, `leaveTypeKey`, `start`, `end`, `reason?`, and `replacementId?`. Workdays are calculated by the backend; a supplied `workingDays` must match. |
| GET/PATCH | `/api/v1/leave-requests/{id}/` | Read a scoped request or correct a `PENDING` request. Correction accepts `leaveTypeKey?`, `start`, `end`, `reason?`, and `replacementId?`; owner or in-scope HR only. |
| POST | `/api/v1/leave-requests/{id}/approve`, `/reject`, `/cancel`, `/withdraw` | Apply the corresponding domain transition. Rejection requires a reason. `withdraw` requests cancellation of an approved leave and requires manager/HR decision via `approve_withdraw` or `reject_withdraw`. |
| POST | `/api/v1/leave-requests/{id}/amend` | Create a correction request for an approved leave. The body may provide `start`, `end`, `reason`, and `replacementId`; omitted fields retain the original value. Approval cancels the original request in the same transaction. The existing frontend `/amend` action submits the unchanged values as a compatibility path. |
| GET/POST | `/api/v1/leave-requests/{id}/comments/` | List/add comments for request participants. Confidential request comments are restricted to in-scope HR. Comment bodies are append-only and limited to 4,000 characters. |
| GET | `/api/v1/leave-requests/{id}/events/` | Read append-only request event history. Confidential event reasons are only returned to in-scope HR. |

Out-of-scope request IDs return 404. Invalid transitions and idempotency conflicts return 409, permission failures 403, validation failures 422, and malformed payloads 400. Each transition/correction/comment records its actor and action; sensitive reasons are redacted from audit snapshots for confidential leave.

The legacy `/api/v1/holidays/` API remains available for one-day Jalali `PublicHoliday` entries and uses the same superuser-only write boundary. Its DELETE operation is logical deactivation and requires a reason.

### Phase F frontend integration APIs

These endpoints back the remaining frontend pages. They require an authenticated session unless noted. Role and organization scope are checked by the backend; the frontend's role guards are not authorization controls.

| Method | Endpoint | Contract |
|---|---|---|
| GET/POST/PATCH | `/api/v1/leave-types/`, `/api/v1/leave-types/{id}/` | Read requestable types or manage types as HR/admin. Responses use the frontend camel-case `LeaveType` shape. |
| GET | `/api/v1/balances/?year={year}&employee={id?}` | Return ledger-derived balance projections for self, direct reports, or assigned HR scope. Reconciliation failures return 409. |
| GET | `/api/v1/entitlements/?year={year}` | List in-scope HR entitlements. |
| POST | `/api/v1/entitlements/{id}/adjust` | Append a ledger adjustment; `{days, reason}` is required. |
| POST | `/api/v1/entitlements/import/?dry_run=0\|1` | Validate CSV (`personnel_code,type,year,days`). Commit is all-or-nothing and uses the entitlement ledger. |
| POST | `/api/v1/hr/absences/` | Create an absence for an employee in the caller's HR scope. HR-originated requests enter `APPROVED` directly through `submit_request`; exactly one `submit` event records the transition from empty to approved. `Idempotency-Key` is required; the payload fingerprint covers employee, type, dates, working days, reason, and replacement. The request, event, audit entry, ledger posting, and idempotency record commit atomically. |
| GET | `/api/v1/employees/`, `/api/v1/companies/`, `/api/v1/departments/` | Read employee/organization rows scoped to the caller. Employee search accepts `q`. Employee creation is HR/admin; company and department writes are admin-only. |
| GET/POST | `/api/v1/employees/{id}/contract-periods/` | Read/add validated employee work-contract periods; HR must have scope for the employee. |
| GET | `/api/v1/coverage/?from={date}&to={date}` | Aggregate approved absences per department/day for the caller's HR or manager scope; maximum 93 days. |
| GET | `/api/v1/reports/{kind}` | Return aggregate series for `absences`, `balances`, `trends`, or `process-health`; small groups are suppressed using `privacy.min_group_size`. The `bradford` option returns a note directing users to the scoped Bradford page. |
| GET/POST | `/api/v1/admin/settings/` | Read/validate/audit schema-defined settings; system-admin only. |
| GET | `/api/v1/admin/jobs/` | Returns an empty list until persistent job-run records are implemented; system-admin only. |
| GET | `/api/v1/audit/events/` | Return recent audit rows for system admins, or request-related rows within HR scope. |
| GET | `/api/v1/policy/client` | Return actual employee-specific calendar work-pattern values. Hourly leave and auto-cancel remain disabled until backend policy support exists. |
| GET/POST | `/api/v1/hr/bradford-notes/` | Read/upsert notes for employees in HR scope. |
| GET/POST | `/api/v1/leave-requests/{id}/attachments/` | List or upload a PDF/PNG/JPEG file up to 10 MiB for a visible request. Files are stored under generated private paths; contents are signature-checked. |
| GET | `/api/v1/leave-requests/{id}/attachments/{attachmentId}/` | Authenticated download for a visible request participant; attachment IDs are scoped to that request and responses are private/no-store. |
| GET | `/api/v1/ready/` | Frontend health check; the HTTP client maps readiness and database checks into the UI health shape. |

Demo data is selected only in development. Production builds always use the HTTP API and do not substitute demo rows after API errors. Report file exports and secure request attachments remain explicitly unavailable.

### Schema endpoints
- `GET /api/v1/schema/` — Implemented via drf-spectacular
- `GET /api/v1/docs/` — Implemented via Swagger UI

## 4. Planned but Unimplemented
- Frontend management screens for range holidays, work patterns, and policy versions
- backend-authoritative hourly leave calculations tied to work patterns and holidays
- leave-year configuration, rollover, expiry, and their ledger operations
- persistent scheduler/job-run records and report file exports
- password reset/onboarding APIs

## 5. Notes
- Pagination, filtering, and idempotency are enforced on the Phase D leave-request API, not globally on unrelated API resources.
- The contract is intentionally conservative and aligned with the current frontend surface rather than introducing unsupported domain commitments.
