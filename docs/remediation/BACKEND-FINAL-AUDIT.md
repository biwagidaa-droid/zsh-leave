# Independent Backend Final Audit

**Audit date:** 2026-11-02  
**Scope:** Django/DRF backend, PostgreSQL, tests, deployment/backup evidence and remediation documentation. `frontend/` was not inspected for implementation changes and was not modified.  
**Repository baseline:** branch `main`, `HEAD`/`origin/main` at `f0ed8d6` (`P18`); clean worktree before audit. Recent commits: `f0ed8d6 P18`, `471c41a P18`, `d2a2846` merge, followed by P17–P11.  
**Audit-created changes:** central employment enforcement in `authorization_context`; service/session expiry regression tests; an existing workday-estimate test now uses scoped HR to test date validation without bypassing caller authorization; backup inventory test now checks the active DB vendor.

## Executive result

The core backend remediation is substantially more complete than several older remediation reports claim. In particular, current code includes effective-employment checks, invitation/activation, explicit global LeaveType permissions, scoped sites/departments, entitlement import/ledger, Bradford reporting, scheduled jobs, export APIs, attachment security, notification outbox, and backup/restore scripts. Those claims were checked against current code and tests, not accepted from prior reports.

**Not production-ready.** The full backend suite passes on PostgreSQL 17 in a disposable environment. Production topology, runtime database roles, deployed systemd timer, external SMTP, attachment volume/scanner, monitoring, and offsite backup are not configured or evidenced. A direct SQL `TRUNCATE` can still remove PostgreSQL append-only audit rows; row triggers only block `UPDATE`/`DELETE`.

## Reproducible command catalog

The focused test names in the findings table were included in the corresponding complete-suite commands below; these commands define the exact execution environment and result for those findings.

**CMD-SQLITE-FULL** (from repository root):

```sh
docker run --rm -v "$PWD:/workspace" -w /workspace python:3.14-slim sh -eu -c \
	'pip install --no-cache-dir -q -r backend/requirements.txt; cd backend; \
	 DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test --verbosity 0'
```

Observed in the final post-auth-change run: exit 0; 378 tests, 14 PostgreSQL-only skips.

**CMD-POSTGRESQL-FULL** (from repository root; the network/container and random password are disposable):

```sh
docker run --rm --network "$PG_TEST_NETWORK" \
	-e ZSH_DB_NAME=audittest -e ZSH_TEST_DB_NAME=test_audittest \
	-e ZSH_DB_USER=postgres -e ZSH_DB_PASSWORD="$PG_TEST_PASSWORD" \
	-e ZSH_DB_HOST=pgtest -e ZSH_DB_PORT=5432 \
	-v "$PWD:/workspace" -w /workspace python:3.14-slim sh -eu -c \
	'pip install --no-cache-dir -q -r backend/requirements.txt; cd backend; \
	 DJANGO_SETTINGS_MODULE=config.settings_postgres_test python manage.py test --verbosity 0'
```

Observed on PostgreSQL 17.11 after final changes: exit 0; 378 tests, zero skips.

For every finding below, the named Django test/module label is its regression test; its exact executable suite command is `CMD-SQLITE-FULL` and/or `CMD-POSTGRESQL-FULL` above unless the row gives a separate direct command. The direct PostgreSQL `TRUNCATE` proof command is fully listed in `POSTGRESQL-EVIDENCE.md`.

**CMD-CHECKS** (from `backend/` in the same disposable Python image):

```sh
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py check
DJANGO_SETTINGS_MODULE=config.settings_test python manage.py makemigrations --check --dry-run
python -m compileall -q config leave zsh_core
```

Observed: all exit 0; `No changes detected`. The production security check was `DJANGO_SETTINGS_MODULE=config.settings_prod python manage.py check --deploy --tag security` with dummy `ZSH_SECRET_KEY`, `ZSH_ALLOWED_HOSTS`, DB user/password/host and `/tmp` attachment root; exit 0, no system-check issues.

## Findings

| Status | Finding | Source files | Root cause / code change | Regression test, command, observed result | Remaining limitation |
|---|---|---|---|---|---|
| FIXED AND VERIFIED | Current employee and manager authorization observes inclusive employment dates and requires an activated account; expired or unactivated users lose roles even on direct service calls. | `backend/leave/authorization.py`, `backend/leave/employment_services.py`, `backend/leave/authentication_classes.py` | Session auth already checked account access; central `authorization_context` did not. It now returns no profile/roles for an ineligible or unactivated employee. | `test_expired_manager_cannot_approve_direct_service_call`, `test_unactivated_employee_profile_gets_no_direct_service_roles`, `test_existing_session_is_rejected_after_employment_end_date_passes`; `CMD-SQLITE-FULL` and `CMD-POSTGRESQL-FULL` passed. | Immediate browser-session invalidation occurs on the next authenticated request; no token/session-version revocation system exists. |
| FIXED AND VERIFIED | HR operational scope does not gain self or direct-manager records through role unions; global LeaveType writes require explicit global permission. | `backend/leave/authorization.py`, `backend/leave/admin_services.py`, `backend/leave/frontend_api_views.py` | HR operation selectors use `scoped_hr_employees`; LeaveType mutations use `MANAGE_GLOBAL_LEAVE_TYPES`. | `test_department_scope_excludes_self_and_manager_union_for_hr_operations`, `test_scoped_hr_cannot_create_or_mutate_global_leave_types`, `test_global_admin_can_manage_and_audit_leave_types`; full suites passed. | Broadly reviewed API behavior is tested; future endpoints must use the same selectors and permission service. |
| FIXED AND VERIFIED | Cross-company, cross-department, and Site/company IDOR paths are rejected on tested CRUD, entitlement, contract, Bradford, attachment, and export routes. | `backend/leave/authorization.py`, `backend/leave/hierarchy_services.py`, `backend/leave/export_views.py`, `backend/leave/frontend_api_views.py` | Scoped querysets and model relationship validation gate object lookup/mutation. | `test_company_scope_rejects_foreign_hr_targets_without_side_effects`, `test_site_company_and_employee_site_relationships_are_validated`, `test_scoped_hr_export_cannot_cross_company`, attachment cross-scope tests; full suites passed. | This is route/test evidence, not proof for arbitrary SQL, future endpoints, or production data. |
| FIXED AND VERIFIED | Invitation tokens are hashed, one-time, expiring, rate-limited, and activation/password flows are audited without raw token storage. | `backend/leave/invitation_services.py`, `backend/leave/invitation_views.py`, `backend/leave/throttling.py` | Invitation tokens are SHA-256 stored and consumed conditionally under row locks; requests use configured DRF throttles. | `leave.tests.test_invitations` (including raw-token, expiry, suspension, concurrent-consumption and rate-limit cases); full suites passed. | SMTP delivery is not tested against a real provider; invitation send is synchronous to avoid persisting a raw activation token. |
| FIXED AND VERIFIED | HR-created absence, workflow idempotency, ledger transitions and CSV duplicate rejection/rollback are covered. | `backend/leave/frontend_api_views.py`, `backend/leave/services.py`, `backend/leave/entitlement_import_services.py`, `backend/leave/entitlement_services.py` | HR absence creates one approved request/event/audit; import revalidates in transaction and ledger writes are idempotent. | `test_hr_absence_is_directly_approved_and_idempotent`, `test_hr_absence_rejects_unauthorized_and_rolls_back_invalid_submission`, `leave.tests.test_entitlement_import`, `leave.tests.test_entitlement_ledger`; complete PostgreSQL suite passed. | Business policy values and production imports/data remain owner-controlled. |
| FIXED AND VERIFIED | Department and manager cycles, Site-company consistency, and current manager eligibility are validated on model/queryset mutation paths. | `backend/leave/hierarchy_services.py`, `backend/leave/models.py` | Hierarchy mutations serialize through company row locks; validators check cycles, company and active employment; protected queryset writes route through model validation. | `leave.tests.test_hierarchy_integrity` (self/multi-node cycles, bulk writes, Site relationship, concurrent manager update); complete PostgreSQL suite passed. | Raw SQL/admin-level edits can bypass application validation; periodic hierarchy diagnostics are not monitoring evidence. |
| FIXED, NOT FULLY VERIFIED | Bradford backend calculation and endpoint are implemented, scoped, confidential-type filtered, paginated, and withhold incomplete partial-day data. | `backend/leave/bradford_services.py`, `backend/leave/frontend_api_views.py`, `backend/zsh_core/reports.py` | The report uses calendar-day `S² × D`, clips to employment, and marks results `provisional`. | `leave.tests.test_bradford` including formula, scope, confidentiality, dates, partial days and pagination; complete suites passed. | Business policy is explicitly provisional and needs HR/legal approval; this is not a certified operational Bradford policy. |
| FIXED AND VERIFIED | CSV duplicate detection covers in-file and stored business keys, and mixed-invalid commits are all-or-nothing. | `backend/leave/entitlement_import_services.py`, `backend/zsh_core/imports.py`, `backend/leave/frontend_api_views.py` | Shared parser/validator plus transaction-time revalidation and entitlement uniqueness. | `leave.tests.test_entitlement_import` (including concurrent duplicate import); complete PostgreSQL suite passed. | No import against production data was performed. |
| FIXED AND VERIFIED | Export routes are registered, scoped, confidential-data redacted, formula-safe, bounded, and audited. | `backend/leave/export_views.py`, `backend/leave/workflow_views.py` | Exports derive rows from authorized querysets and reuse report/balance visibility policy. | `leave.tests.test_exports`: employee, manager, HR, confidential CSV, formula injection, executive suppression, Bradford, limits, authentication and audit; complete suites passed. | No Frontend workflow or production export path was exercised. |
| PARTIALLY FIXED | Audit/history ORM mutation, queryset mutation, and direct SQL `UPDATE`/`DELETE` are blocked by model rules and database triggers; direct SQL `TRUNCATE` is not blocked. | `backend/leave/audit_services.py`, `backend/leave/models.py`, `backend/leave/migrations/0014_append_only_history_guards.py`, `backend/leave/migrations/0015_auditevent_source.py` | Row-level triggers do not intercept `TRUNCATE`; deployment table ownership/privileges are not defined. No unsafe trigger migration was retained because it broke Django PostgreSQL test flush. | `leave.tests.test_append_only_integrity` passed on PostgreSQL for ORM, bulk and SQL UPDATE/DELETE. Separate committed SQL proof: insert one AuditEvent; `TRUNCATE TABLE public.leave_auditevent`; count returned 0. | Production app role must not own these tables and must lack `TRUNCATE`; independent INSERT privilege/audit trust also needs least-privilege role design. Gate 6 remains NOT VERIFIED. |
| FIXED, NOT FULLY VERIFIED | Attachment validation, private filesystem permissions, scoped download, failure cleanup, and restore checksum logic are implemented. | `backend/leave/attachment_security.py`, `backend/leave/attachment_storage.py`, `backend/leave/attachment_services.py`, `backend/leave/frontend_api_views.py` | Private root is outside repository with `0700` directories/`0600` files; MIME/signature/parser checks and optional scanner are enforced. | `leave.tests.test_attachment_security`; backup `verify_backup` checks hashes; independent PostgreSQL restore drill restored a synthetic 37-byte attachment with matching SHA-256. | Real persistent volume, ownership under service account, malware scanner, and production download path are not configured. Empty scanner setting means `unscanned`, not clean. Gate 9 remains NOT VERIFIED. |
| FIXED, NOT FULLY VERIFIED | DB-backed jobs have uniqueness, retry, lease, heartbeat, idempotency, and readiness; one-shot scheduler was executed after restore. | `backend/leave/job_services.py`, `backend/leave/management/commands/run_scheduled_jobs.py`, `deploy/systemd/` | Jobs persist `JobExecution`, use PostgreSQL advisory lock, and record heartbeat; a sample systemd unit/timer exists. | `leave.tests.test_scheduled_jobs`; isolated restore drill ran `run_scheduled_jobs`, got `notification_delivery` `succeeded`, heartbeat true, `/health`=200 and `/ready`=200. | The systemd timer is not installed/enabled in a managed host. No production worker/timer/alert evidence. Gate 8 remains NOT VERIFIED. |
| FIXED, NOT FULLY VERIFIED | Notification outbox distinguishes `queued/sent/delivered/failed/unavailable`, revalidates recipients and avoids retry duplicates; no external provider receipt exists. | `backend/leave/notification_services.py`, `backend/leave/models.py`, `backend/leave/job_services.py`, `docs/notifications-fa.md` | Django email abstraction and DB job queue; SMTP acceptance is `sent`, not `delivered`. | `leave.tests.test_notification_delivery`; final 378-test suites passed on SQLite and PostgreSQL. | No real SMTP/provider credentials, bounce webhook, push, or SMS; external delivery status not proven. |
| FIXED, NOT FULLY VERIFIED | Backup/restore scripts encrypt a coordinated database/media snapshot and an isolated PostgreSQL restore drill succeeded. | `deploy/backup/`, `backend/leave/management/commands/verify_backup.py`, `docs/backup-restore-fa.md` | Scripts require quiescence attestation, age recipient/identity, explicit app version, a separate empty `zsh_restore_*` target and inventory comparison. | This audit repeated a fresh two-container PostgreSQL 17.11 drill after migration 0020; encrypted checksums, migrations, counts, FK, media hash, ledger, scheduler and readiness all passed. | No production schedule, offsite copy, retention service, alert, production volume or production restore. Production backup remains **NOT VERIFIED**; Gate 10 remains NOT VERIFIED. |
| BLOCKED | Production monitoring/log aggregation/alerting and deployed infrastructure are absent. | `backend/config/settings_base.py`, `backend/config/settings_prod.py`, `deploy/` | Logging is console-only; repository has no production web/proxy/backup/monitoring stack or managed DB-role setup. | Production-settings checks passed with dummy environment only; tests use Django test clients and disposable services. | No real host, proxy, SMTP, scanner, database role, systemd timer, monitoring, offsite storage, or alerting evidence. |

## Gate results

| Gate | Result | Evidence / limitation |
|---|---|---|
| 1 — Authorization and scope | PASS | Backend regression suites cover HR/self/manager scope unions, cross-company IDOR, global LeaveType permission, and direct expired-manager service calls. |
| 2 — Confidentiality | PASS | API, in-app notification, Bradford, report aggregation, balance and CSV/XLSX export tests cover confidential paths. This does not certify future routes. |
| 3 — Employment lifecycle | PASS | Inclusive boundary tests plus active-session expiry and direct service rejection. Session invalidation is enforced on the next request, not by a token revocation service. |
| 4 — Account activation | PASS | Hashed one-time token, expiry, replay/concurrency, revocation, rate limit, and password tests pass. |
| 5 — Data integrity | PASS | Department/manager cycles, Sites, import duplicate/rollback, entitlement ledger, PostgreSQL concurrency all pass. |
| 6 — Audit integrity | NOT VERIFIED | PostgreSQL UPDATE/DELETE guards pass, but direct TRUNCATE was proven to delete rows; DB grants/ownership are not configured. |
| 7 — PostgreSQL | PASS | Fresh PostgreSQL 17.11 full backend suite: 378 tests, 0 skips; all current migrations applied. This is not production DB evidence. |
| 8 — Jobs | NOT VERIFIED | One-shot command/heartbeat and readiness passed in an isolated drill; no deployed systemd timer/worker evidence. |
| 9 — Attachments | NOT VERIFIED | Private storage/access tests and synthetic restore hash passed; production volume and scanner are absent. |
| 10 — Operations | NOT VERIFIED | Isolated backup/restore succeeded; production deployment, offsite schedule, alerts, and real recovery objectives are not evidenced. |

## Test and tooling summary

Full SQLite command: `DJANGO_SETTINGS_MODULE=config.settings_test python manage.py test --verbosity 0` inside a disposable `python:3.14-slim` container with `backend/requirements.txt`; **378 tests, 14 skips, 0 failures**. Skips are PostgreSQL-specific.

Full PostgreSQL command: `DJANGO_SETTINGS_MODULE=config.settings_postgres_test python manage.py test --verbosity 0` inside `python:3.14-slim` connected to a disposable PostgreSQL 17.11 container; **378 tests, 0 skips, 0 failures**.

`manage.py check`: exit 0. `makemigrations --check --dry-run`: exit 0, `No changes detected`. `python -m compileall -q config leave zsh_core`: exit 0. `manage.py check --deploy --tag security` with ephemeral dummy secrets/hosts: exit 0, no system check findings. `git diff --check`: exit 0.

No project formatter/linter/type-check configuration was found. Generic Black check returned exit 1 (“7 files would be reformatted”); default Flake8 returned exit 1 with 150 E501 findings plus one unused-import finding across the selected files; Mypy returned exit 1 with four findings (dynamic `models.Manager.from_queryset` base and three optional-profile narrowing warnings). These generic checks are not configured project gates and were not “fixed” by broad reformatting or changing tests.
