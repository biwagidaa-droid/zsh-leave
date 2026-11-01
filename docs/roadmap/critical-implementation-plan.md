# Critical Implementation Plan: Authentication, RBAC, Leave, Entitlements, and API

**Audit date:** 2026-11-01  
**Scope:** Repository and dependency audit for the next operational implementation phase.  
**Change boundary:** This audit created this document only. No application code, dependency manifest, or migration was modified.

## 1. Executive summary

The repository has a usable foundation, but it is not yet an operational leave-management application:

- The backend is Django 5.2 + DRF, with PostgreSQL as the intended production database and SQLite as the test fallback. It currently exposes health/readiness, calendar, holiday, work-pattern, policy, and workday-estimate endpoints. It has no login/session lifecycle endpoints, leave-request API, entitlement API, or persisted application-role model.
- The frontend is a React/TypeScript/Vite application with a broad, typed API interface and a development-only demo adapter. Its HTTP adapter already assumes many endpoints that the backend does not implement.
- Pure domain logic for workflow, balances, policy, permissions/redaction, dates, and workdays is reusable. The primary gap is not a blank domain; it is the missing authenticated application/service/API path that safely connects this logic to persisted data.
- Existing models include `EmployeeProfile`, `LeaveType`, `LeaveRequest`, `LeaveEntitlement`, `EntitlementEvent`, audit/history records, and calendar-policy data. These are a foundation, not a complete or consistently enforced operational schema.
- PostgreSQL-specific behavior, actual migration application, and concurrency guarantees have not been verified against PostgreSQL. SQLite results do not establish production data-integrity behavior.

**Recommended order:** confirm policy and accounting decisions → implement session authentication → implement database-backed, scoped RBAC → expose leave workflows through authorized services and APIs → implement entitlement events and a consistent balance contract → connect and verify frontend pages against those APIs → validate the whole migration/API path on PostgreSQL.

## 2. Audit baseline and evidence

### Repository shape

- Backend: `backend/config`, `backend/leave`, and framework-independent `backend/zsh_core`.
- Frontend: `frontend/src/api`, `frontend/src/state`, `frontend/src/lib`, shared components, and role-oriented pages.
- Database: Django migrations `0001_initial`, `0002_calendarholidayhistory_leavepolicyversion_and_more`, and `0003_publicholiday_is_active_publicholiday_updated_at_and_more`.
- Design and readiness documents: [backend architecture](../architecture/backend.md), [database architecture](../architecture/database.md), [access-control design](../architecture/access-control.md), [API contract](../api/api-contract.md), [data model](../data-model.md), [workflow design](../workflows.md), [security design](../security.md), [test plan](../testing.md), and [release-readiness report](../reports/release-readiness-report.md).

### Existing verification evidence

The repository's latest recorded release-readiness report says backend tests, frontend tests, frontend build/type-check, dependency audits, Django checks, and migration-drift checks passed in their reported environments. It also explicitly says PostgreSQL migrations/concurrency, end-to-end authorization, backup/restore, and production readiness remain unverified. Earlier phase reports likewise report SQLite caveats and no PostgreSQL service available. Treat these as recorded prior results, not as tests rerun for this audit.

The worktree was clean at the start of this audit. No application code or dependencies were changed.

## 3. Reusable implementation inventory

### Backend

| Existing component | Reuse in implementation | Important boundary |
|---|---|---|
| `backend/zsh_core/workflow.py` | Canonical transition rules and typed workflow errors. | It accepts an actor role in its context; the API/service must derive that role from authenticated, scoped server-side authorization. |
| `backend/leave/services.py` | Starting point for transactional request submission and state changes. | It is not yet an authorized application boundary. `apply_event` loads by raw request ID and takes a caller-provided role; it does not itself enforce request ownership, manager relationship, or HR company scope. |
| `backend/zsh_core/permissions.py` | Pure policy for request visibility, decisions, redaction, calendars, notifications, and visible balance types. | Must be connected to ORM selectors and serializers consistently; a pure helper alone does not filter database querysets or protect every API. |
| `backend/zsh_core/balance.py` | Decimal-based, pure balance formula, year allocation, and carry-over calculation. | Current formulas derive usage from leave-request status; do not also subtract request usage through new ledger events unless the accounting contract is deliberately changed. |
| `backend/leave/calendar_services.py` | Effective policy/work-pattern resolution and authoritative workday calculation. | Policy and work-pattern APIs currently use a temporary superuser boundary; UI/configuration and organizational RBAC are incomplete. |
| `backend/leave/models.py` | Existing company/site/department/profile, leave type/request/entitlement, event, audit, and policy models. | Several models and constraints are only partial relative to the design docs; see database risks below. |
| `backend/leave/admin_services.py` | Transactional settings and holiday operations with audit/history writes. | Reuse its explicit validation/audit/service pattern, but do not assume it solves role/scope authorization. |
| `backend/config/settings_base.py` | Django sessions, `SessionAuthentication`, default `IsAuthenticated`, CSRF middleware, cookie flags, password validators, and DRF throttle rates. | Throttle rates alone do not enable a throttle class. Production hardening and actual session/CSRF behavior need tests. |
| `backend/leave/calendar_views.py` | Existing endpoint response helpers, date parsing, employee-profile lookup, and current calendar scoping. | Authorization differs by endpoint and includes group/superuser checks; centralize/reuse authorization policy rather than copying these checks. |

### Frontend

| Existing component | Reuse in implementation | Important boundary |
|---|---|---|
| `frontend/src/api/contract.ts` | The typed `Api` interface is the seam between pages and transport. | Keep demo and HTTP implementations behaviorally compatible as API features arrive. |
| `frontend/src/api/http.ts` | Shared fetch wrapper, credentials, CSRF header, JSON/error parsing, and 401 event. | It currently points at many routes that do not exist on the backend. Define and test endpoint paths/payloads against the backend contract. |
| `frontend/src/api/demo.ts` and `frontend/src/api/mode.ts` | Development fixture/demo behavior and the production prohibition on demo mode. | Demo data is not evidence that the backend feature works and must never be a fallback for API errors. |
| `frontend/src/state/Auth.tsx` | Existing auth context, login/logout actions, session refresh, and expiry listener. | `refresh` currently treats every error as logged-out state; distinguish a real 401 from connectivity/server failure so errors are not hidden as an unauthenticated session. |
| `frontend/src/lib/roles.ts` and `frontend/src/App.tsx` | Role labels, frontend route guards, and page routing. | Route guards are UX only; every API/service must independently authorize. |
| `frontend/src/api/errors.ts`, `frontend/src/lib/useAsync.ts`, `frontend/src/state/Toast.tsx`, `frontend/src/components/ui.tsx` | Shared API error display, async loading/error states, feedback, and form controls. | Preserve explicit errors; do not convert unsupported endpoints or failures to success-shaped defaults. |
| `frontend/src/state/Notifications.tsx` | Notification context and refresh integration. | A real notifications API and persistence/job path are not present in the backend. |
| `frontend/src/pages/RequestsPages.tsx`, `HrPages.tsx`, `OrgPages.tsx`, `AdminPages.tsx`, `CalendarPages.tsx` | Existing user-facing screens and their API calls. | Verify each page against actual backend responses; the current frontend surface is materially broader than the backend API. |

## 4. Dependency and runtime analysis

### Backend dependencies

`backend/requirements.txt` declares Django `>=5.2,<5.3`, DRF `>=3.15,<4`, `psycopg[binary]`, `drf-spectacular`, Gunicorn, `openpyxl`, and `argon2-cffi`. Django's built-in auth/session/permission facilities are already installed; no separate authentication, role-management, task-queue, or API-client dependency is required to begin the requested work.

Important implications:

- The Python requirements use version ranges and there is no checked-in backend lock/constraints file visible in the repository. Record and reproduce the resolved Python dependency set in CI/deployment before calling builds reproducible.
- `argon2-cffi` is installed as a declared dependency, but `settings_base.py` does not configure Argon2 as a password hasher. Decide whether Argon2 is a requirement, configure it with a safe legacy-hash upgrade path, and test existing Django password verification before changing hasher ordering.
- DRF throttle rates are configured, but a throttle class is not configured in `REST_FRAMEWORK`; rate values alone do not implement login throttling.
- `openpyxl` is relevant to future XLSX import/export, not a prerequisite for the first session-auth or leave-request API slice. Keep XLSX import out of initial ledger writes until parsing, validation, dry-run, and audit behavior are specified.
- No extra dependency should be added for standard session authentication, serializers, or role checks without a specific implementation need.

### Frontend dependencies

`frontend/package.json` declares React, React DOM, React Router, TypeScript, Vite, and the React Vite plugin; a `package-lock.json` is present. The existing transport uses browser `fetch` and same-origin `/api/v1` paths, so the current design does not require a separate HTTP client or token-storage library.

### Environment and deployment boundary

The base settings select PostgreSQL by default; test settings use SQLite. Development settings enable `CORS_ALLOW_ALL_ORIGINS`, but no CORS middleware/dependency is declared. Prefer same-origin frontend/API deployment as already assumed by `http.ts`; if cross-origin deployment is required, define and test an explicit origin/CSRF policy rather than relying on the development setting. No CI workflow file was found in `.github/workflows/`.

## 5. Database risks and migration dependencies

### Existing migration/user dependency

The current app migration chain is `0001` → `0002` → `0003`. `0001_initial` already creates the current domain tables and has `migrations.swappable_dependency(settings.AUTH_USER_MODEL)`; settings explicitly use Django's default `auth.User`. All later user references are therefore tied to that migration history.

**Recommendation:** retain Django's existing user model and add role/scope tables unless there is a firm, pre-production requirement for a custom user model. Switching `AUTH_USER_MODEL` after these migrations/data exist is a high-risk schema/data migration and must not be treated as an ordinary feature change. Confirm the target database has no applied migration or user data before considering a model swap.

New migrations must be forward migrations after `0003`; do not rewrite migrations that may have been applied. Before applying them to any persistent environment, inspect `showmigrations`, database engine/version, existing row counts/data, and backup/restore status. Use rehearsed data migrations with checkpoints and a documented rollback/forward-repair path.

### Integrity and portability risks

1. **PostgreSQL requirements are not yet proven.** `PublicHoliday` uses `UniqueConstraint(..., nulls_distinct=False)`, documented as requiring PostgreSQL 15 or newer. The existing test database is SQLite, where that constraint is not enforced equivalently. Test the actual migrations and constraint behavior against the supported PostgreSQL version.
2. **Concurrency guarantees depend on PostgreSQL.** `select_for_update` is relied on in service code, but SQLite does not provide equivalent row-lock semantics. Leave overlap protection and balance mutations need PostgreSQL concurrency tests, not only unit tests or SQLite integration tests.
3. **Request overlap is not a database exclusion constraint.** Current submission code uses an employee-row lock and an application-level overlap query. Verify that every submission path locks the same employee row and consider a PostgreSQL constraint only after the actual overlap policy (including pending, amendments, and approved requests) is confirmed.
4. **Entitlement event records are not currently immutable.** `EntitlementEvent` does not inherit `_AppendOnly`; it can be updated/deleted through ordinary ORM paths. Existing append-only model guards are Python-level and are not equivalent to database-enforced immutability.
5. **Current entitlement is a mutable projection.** `LeaveEntitlement` stores `base_days`, `carry_over_days`, and `manual_adjustment`; the event stores before/after JSON and optional unique idempotency key, but has no implemented service tying it to every entitlement change.
6. **Cross-entity scope invariants are not all database-enforced.** For example, employee manager/company consistency and policy/work-pattern effective-date overlap rely on service/model validation. Review race conditions and enforce critical invariants at the database layer where portable or safely PostgreSQL-specific.
7. **Migration/data bootstrap is unresolved.** There is no confirmed inventory of production users, HR groups, employee profiles, opening entitlements, or request history. Role conversion and ledger initialization must be explicit, auditable, idempotent, and tested against a representative copy.
8. **Append-only audit records need operational protection.** Model overrides do not stop direct SQL or privileged bulk operations. Decide whether database roles/triggers are needed for audit/ledger immutability and define retention before production use.

### Proposed migration order

1. **Preflight:** verify PostgreSQL 15+ (or explicitly revise the holiday constraint requirement), applied migration state, backup/restore, baseline row counts, and supported auth model.
2. **Authorization schema:** add role definitions/assignments and scope fields/history if the selected design needs them. Use `0003` as the dependency base and the swappable Django auth dependency. Add DB uniqueness/check constraints for assignment identity and valid scope combinations.
3. **Authorization data migration:** map existing Django `HR` groups and approved superuser/admin accounts to the new authorization representation, with company scopes sourced from validated employee/org data. Fail closed for ambiguous or unmappable records; do not silently grant global HR.
4. **Leave/accounting schema:** only after the consumption model is approved, add any request idempotency/audit fields, immutable ledger constraints/columns, and required indexes. Separate schema changes from large data backfills where practical.
5. **Ledger bootstrap/backfill:** record opening entitlement state and, if the selected model requires it, historical consumption. Use stable idempotency keys, run in a transaction/batch strategy appropriate to table size, compare totals to the pre-migration balance implementation, and produce a reconciliation report before cutover.
6. **API cutover:** deploy schema and compatible code before enabling new writes; make the new write path authoritative only after reconciliation and PostgreSQL tests pass. Do not dual-write two independent balance authorities.

## 6. Architectural conflicts and open decisions

| Conflict / open decision | Current evidence | Resolution required before implementation |
|---|---|---|
| Design RBAC vs operational authorization | Docs specify multiple scoped roles and `Role`/`UserRole`; the ORM has no role-assignment model. Calendar code uses Django group `HR`, and management endpoints use `is_superuser`. | Approve one source of truth for role assignments/scopes, migration from existing groups, role lifecycle, and admin-vs-data visibility. |
| Pure permission rules vs API enforcement | `zsh_core/permissions.py` implements pure visibility/redaction policy, but it is not yet a shared ORM/API authorization layer for all endpoints. | Build common server-side authorization/selectors and serializers; enforce queryset scoping before object lookup and redaction on every output surface. |
| Workflow role vs trusted actor | `LeaveRequestService.apply_event` accepts `role` from its caller and loads requests by ID; state-machine validation does not establish caller ownership or reporting relationship. | Authorize against authenticated user, employee profile, request owner, manager snapshot, current scope, and status before transition; derive role/context server-side. Return non-disclosing 404 for out-of-scope records as specified. |
| Frontend breadth vs backend contract | `httpApi` implements calls for authentication, requests, balances, entitlements, notifications, HR, employees, reports, settings, and more; backend URL configuration currently exposes health/readiness, calendar/date, holiday, work-pattern/policy, and estimate routes. | Publish an endpoint-by-endpoint contract and implement matching methods/payloads/responses; keep unfinished UI features disabled or explicitly unavailable, not silently demo-backed. |
| Frontend role guard vs security boundary | `App.tsx` gates routes using client-side `User.roles`. | Preserve guards for navigation, but treat the backend as the only authority for permission decisions and visible data. |
| Entitlement ledger vs request-derived usage | `balance.py` calculates used/pending from `LeaveRequest.status`; `LeaveEntitlement` has mutable allocations and `EntitlementEvent` snapshots. Design docs describe the same request-derived formula. | Recommended initial model: leave requests remain the sole source of consumption, while immutable entitlement events record grants, adjustments, imports, and rollovers; `LeaveEntitlement` is a locked projection. Do not create consume/release events in parallel unless switching to a fully journal-derived balance is explicitly approved. |
| Leave-year rules vs calendar-year split | `LeaveEntitlement.year` comments allow Jalali/Gregorian policy; `allocate_by_year` defaults to Gregorian and needs a workday predicate for accurate apportionment. | HR must approve year boundary, timezone, rounding, rollover cap/expiry, partial-year proration, and handling of cross-year requests. Make the year resolver explicit and shared by reads/writes. |
| Organization model gaps | Current ORM has Company, Site, Department, EmployeeProfile, and a manager link. Design docs additionally discuss units, positions, contracts, contract periods, and effective-dated org changes. | Define initial supported scope dimensions and source data. Avoid implementing permissions against unmodeled dimensions or silently treating absent scope as global. |
| Authentication/session assumptions | Django session auth and CSRF middleware are configured; frontend sends cookies and reads a CSRF cookie. There are no backend login/logout/me/password endpoints. | Specify same-origin deployment and CSRF bootstrap/login behavior, session rotation/expiry, disabled-account handling, password reset/provisioning ownership, and login throttling. |
| Service readiness | `backend/leave/services.py` calls `timezone.now()` but does not import `django.utils.timezone` in the audited file. | Correct and test this tightly coupled defect while implementing the service path; do not expose an endpoint that depends on the broken path. |

The following governance decisions remain unresolved in [business decisions](../architecture/business-decisions.md) and [organizational decisions](../reports/phase-09-11-organizational-decisions.md): HR scope, executive aggregation, confidentiality policy, leave-year/carry-over rules, past-dated requests, manager absence/substitution, retention, notifications, and production recovery targets. Keep affected behavior denied, disabled, or explicitly incomplete until approved.

## 7. Detailed implementation plan

### Phase 0 — Confirm policy and technical baseline

1. Record approved behavior for account provisioning, role scope, confidentiality, HR entry, manager substitution/escalation, leave-year boundaries, carry-over, negative balances, amendments/withdrawals, and historical data.
2. Confirm PostgreSQL version and whether migrations `0001`–`0003` have been applied anywhere; inspect representative employee, group, request, and entitlement data without changing it.
3. Lock the identity choice (recommended: keep Django `auth.User`) and define initial role assignment semantics: role, scope kind/id, effective dates, grantor, reason, revocation, and audit.
4. Approve the balance accounting boundary: request-derived consumption with entitlement allocation events (recommended) or a complete event-sourced journal. Specify how historical data will reconcile.
5. Establish a PostgreSQL CI/test target and a dependency-resolution record before declaring database readiness.

**Exit gate:** no unresolved decision that could change permissions, balance amounts, or historical interpretation; representative migration data and PostgreSQL available.

### Phase 1 — Authentication and account lifecycle

1. Implement DRF endpoints matching the existing frontend methods: `POST /api/v1/auth/login/`, `POST /api/v1/auth/logout/`, `GET /api/v1/auth/me/`, and `POST /api/v1/auth/password/`. Align slash behavior and wire into `leave/urls.py`.
2. Use Django session authentication for the existing same-origin cookie model. Add a CSRF-token bootstrap/refresh path if the SPA cannot reliably obtain a token before login; require CSRF on session-changing requests, including login/logout/password changes.
3. Authenticate with Django's supported auth helpers; reject inactive users and users without a valid/active employee profile when an employee identity is required. Do not accept role, employee ID, company ID, or scope as trusted login payload.
4. Return a stable `User` DTO compatible with `frontend/src/api/types.ts`, with server-derived roles and organization/profile data. Keep field visibility minimal and avoid exposing confidential leave type metadata.
5. Define session rotation, expiry, logout invalidation, password validation/hashers, failed-login auditing, and throttling. Configure an actual DRF throttle class or a tested login-specific throttle; the current rate settings are otherwise inert.
6. Update `AuthProvider.refresh` so only an expected unauthenticated response becomes `user = null`; network, server, and malformed-response errors remain visible/retryable.

**Acceptance:** session login/me/logout/password integration tests, CSRF tests, inactive-account tests, login throttling tests, no credentials/session IDs in logs, and frontend refresh/expiry behavior tests. Session cookies remain HttpOnly/Secure in production; CSRF behavior is verified in browser-like tests.

### Phase 2 — Scoped RBAC and privacy enforcement

1. Adopt the approved role model. Minimal recommended schema: role code plus user assignment with explicit scope type/ID, active/effective dates, grantor/revoker, and audit reason. Preserve multi-role users. Avoid a global HR grant unless explicitly approved.
2. Use one backend authorization policy that resolves the current actor, employee profile, roles, and allowed company/site/department scope from the database. Do not derive permissions from frontend role names or request-supplied role values.
3. Provide shared operations such as `require_permission`, scoped queryset selectors, request visibility/decision checks, and serializer redaction. Use `zsh_core.permissions` for pure decisions where possible, but keep database filtering and object authorization in an application layer.
4. Define rules for employee self-access, manager direct-report access using the request's manager snapshot, HR company scope, admin system configuration vs leave data, and aggregate-only executive reporting. Managers must not see confidential type/reason; admin must not inherit leave-record visibility by default.
5. Make authorization checks apply before read/update/action operations. Use a scoped selector so an out-of-scope ID returns the documented non-disclosing 404; avoid unscoped `get(pk=...)` followed by a 403 where existence is sensitive.
6. Add migration/bootstrap of existing HR groups and administrators only after source memberships and company mappings are validated. Audit every new/revoked assignment.
7. Apply a consistent privacy/redaction contract to API responses, calendar events, notifications, comments, exports, and logs; add canary tests spanning every implemented output.

**Acceptance:** role × scope × operation matrix tests at both policy and API levels, cross-company and stale-manager tests, IDOR tests, admin separation-of-duties tests, and confidential canary non-leak tests.

### Phase 3 — Leave request service and API

1. Formalize request input/output serializers and endpoint contracts from [API design](../api.md): list/create, retrieve/update, approve/reject/cancel/withdraw/amend actions, and HR absence recording. Keep error shapes consistent (`code`, `message_fa`, optional `fields`).
2. Add scoped request selectors and explicit service authorization. The service receives the authenticated actor and a server-derived authorization context; it never trusts a `role` supplied by the client.
3. Keep all state transitions in the domain workflow and a single transactional application service. Revalidate permission, current status, request owner/manager snapshot, confidentiality, replacement, policy version, and reason within the operation.
4. Lock rows in a documented order (employee/request, then entitlement projection if required) and keep transition, request update, request event, audit record, and any entitlement projection update in one transaction. Handle concurrent duplicate actions as a conflict, not a false success.
5. Make create/update/approve paths use backend workday and policy resolution. Preserve the existing daily workday API and reject missing policy/configuration rather than estimating silently. Defer hourly requests until backend calculation, work-pattern, and entitlement semantics are specified.
6. Implement amendments and withdrawals exactly as the documented state machine, including the one-active-amendment constraint and atomic resolution of original/amended records.
7. Audit state changes with minimal/redacted data. Do not copy confidential request reason/note text into general audit, notifications, or application logs.
8. Resolve the missing `timezone` import in `backend/leave/services.py` and cover auto-approval, audit timestamps, and failure rollback with tests.

**Acceptance:** every documented transition has unit and API tests; owner/team/HR scope tests cover reads and writes; concurrent create/approve/amend tests run against PostgreSQL; idempotency/conflict behavior and audit transaction rollback are verified.

### Phase 4 — Entitlement allocation ledger and balance APIs

1. Adopt the recommended accounting boundary unless HR explicitly approves a full journal: approved/withdrawal-pending request status remains the source of used leave; pending/escalated status remains the source of reserved leave; entitlement events record allocation changes only.
2. Make `EntitlementEvent` immutable through its model/service boundary and consider database-level protection for production. Give event kinds a controlled set, require actor/reason where applicable, and store structured before/after snapshots. Require a stable idempotency key for imports and rollover.
3. Implement a single transactional entitlement service for grant/set, adjustment, import, and rollover. Lock the `(employee, leave_type, year)` entitlement row, calculate the new projection, append exactly one event, and audit the action in the same transaction.
4. Keep `LeaveEntitlement` as the current allocation projection (`base + carry_over + manual_adjustment`) and reconcile it to its immutable events. Prevent API/model code from changing allocation fields without an event.
5. Use `zsh_core.balance.compute_balance` as the calculation core; supply the approved leave-year resolver/workday weighting and fetch only requests/types within the authorized employee/year scope. Do not return balances for missing entitlement as zero or another fabricated default.
6. Implement balance/entitlement read endpoints, adjustment, and CSV/XLSX import with dry-run. For imports, validate all rows and permissions before commit; report per-row failures; make retries idempotent; guard spreadsheet formulas on exports.
7. Before rollout, backfill opening allocations and compare the new projection and computed remaining/usable balance to the old formula for every migrated employee/type/year. Reconcile cross-year requests with the approved year resolver.
8. If the organization instead chooses a full spend/release journal, design a separate explicit decision and migration: request approval must post an idempotent consumption event, withdrawal/amendment must reverse it exactly once, and balance reads must stop also summing request status. Never mix both sources.

**Acceptance:** decimal and rounding tests, repeated adjustment/import/rollover idempotency, parallel adjustment/approval tests on PostgreSQL, negative-balance policy tests, cross-year reconciliation, and immutable-event tests.

### Phase 5 — Frontend API integration

1. Implement against the shared `Api` contract and existing `httpApi` adapter. Group integration by backend capability: authentication/profile; request list/detail/actions; balances/entitlements; HR administration; notifications; reports/configuration.
2. For every endpoint, document method, URL, query parameters, request/response DTO, pagination, status codes, and error fields in the API contract/OpenAPI. Add contract checks so the frontend does not depend on accidental response shape.
3. Confirm the actual backend route names and trailing-slash convention before wiring paths. `http.ts` currently contains paths that the backend does not expose; remove or clearly gate unsupported methods/pages rather than presenting them as operational.
4. Keep Demo mode isolated to development. Never fall back to demo data on 404, 401, 5xx, or network failure. Keep explicit loading, empty, retry, and permission-denied states.
5. Keep frontend route guards for usability, derive navigation from `/auth/me`, and treat backend permission responses as authoritative. Clear user/role-sensitive cached page state on logout, session expiry, or identity change.
6. Keep request/calendar display redacted according to server response; the frontend must not infer confidential visibility from local role checks.
7. Add focused tests for API URL/payload mapping, session/CSRF behavior, 401 expiry, rejected mutations, and page error states; follow with browser E2E for employee, manager, HR, admin, and executive flows after API availability.

**Acceptance:** no production page depends on demo-only data; every enabled HTTP-mode action maps to a tested backend endpoint; API failures remain visible; user-scope changes cannot display stale data.

## 8. Dependency graph and release gates

```text
Approved business/security decisions
              |
       PostgreSQL preflight
              |
       Authentication
              |
  Scoped RBAC + role bootstrap
        /             \
Leave workflow     Entitlement contract
        \             /
       Backend API + OpenAPI
              |
     Frontend HTTP integration
              |
 PostgreSQL, API, E2E, recovery gates
```

The entitlement contract is a prerequisite to finalizing approval-side balance behavior. The frontend can prepare against the typed contract in parallel, but production integration depends on stable backend contracts and real authentication/RBAC.

**Do not enable production writes until all gates pass:**

- `makemigrations --check --dry-run` is clean and forward migrations apply successfully to a PostgreSQL database at the supported minimum version.
- PostgreSQL constraints, transaction rollback, row-lock behavior, overlap races, unique idempotency, and concurrent approval/adjustment tests pass.
- Role bootstrap and entitlement backfill are rehearsed on representative data and produce zero unexplained reconciliation differences.
- API authorization, IDOR, confidential-data canary, CSRF, session expiry, throttle, and inactive-user tests pass.
- Frontend production build and API/browser E2E pass in HTTP mode without demo fallback.
- Backup/restore and rollback/forward-repair procedures are exercised; operational owners, retention, and recovery targets are approved.

## 9. Current implementation boundary

This plan does not authorize or perform changes to production code, dependencies, migrations, or deployment. The next implementation should begin with the Phase 0 decisions and PostgreSQL preflight, then proceed through the dependency order above. Any unresolved permission or balance policy must remain fail-closed rather than being inferred from demo behavior or design placeholders.
