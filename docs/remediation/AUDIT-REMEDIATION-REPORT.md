# Audit remediation report

## Independent audit status (2026-11-02)

This report records an earlier remediation snapshot. Current evidence supersedes its PostgreSQL/production limitations: the complete backend suite passed against PostgreSQL 17.11, but production DB roles and deployment remain unverified. A new audit found row-level append-only UPDATE/DELETE guards do not block `TRUNCATE`; see [PostgreSQL evidence](./POSTGRESQL-EVIDENCE.md) and [final backend audit](./BACKEND-FINAL-AUDIT.md). Do not interpret the earlier “not verified” statements as current test-environment evidence or as proof of production readiness.

## Outcome

The backend now uses one centralized audit writer for production `AuditEvent`
creation, per-entity allowlisted snapshots, a server request correlation/source
context, and transactional integrations for the sensitive API and service
paths listed in [the coverage matrix](./AUDIT-COVERAGE-MATRIX.md). Audit
insertion failures propagate and roll back the mutation when both writes use
the same database transaction.

No Frontend files were modified.

## Implemented

- Added the centralized audit service with safe model snapshots and payload
  filtering. Bradford note text, leave request free text, comment text,
  attachment filenames, passwords, tokens, and email addresses are excluded.
- Added request correlation/source middleware and the `AuditEvent.source`
  database field.
- Added transactional audit records for EmployeeProfile, Company, Department,
  OrganizationSite, ContractPeriod, BradfordNote, LeaveType, RoleAssignment,
  work pattern/policy, leave workflow/comments/attachments, entitlement ledger
  mutations/imports, settings, holidays, and account lifecycle events.
- Added backend-only admin-gated organization site CRUD endpoints.
- Scoped HR audit queries to their current employee scope and omitted
  before/after snapshots, reason, correlation ID, and source from HR responses.
- Reinstalled the AuditEvent database append-only guard after its table rebuild
  in the new migration.
- Added regression tests for requested CRUD, ledger, import, failure rollback,
  privacy, actor integrity, and cross-company audit-query isolation cases.

## Residual risk / not certified

- Application service/API writes are audited; arbitrary ORM writes and SQL
  inserts can bypass this service. Database guard triggers protect against
  UPDATE/DELETE, not unauthorized INSERTs.
- No HTTP mutation endpoint exists for ContractPeriod update/delete,
  WorkPattern update/delete, or BradfordNote delete. Future endpoints need
  their own before/after audit and tests.
- Account lifecycle events identify the employee and current profile state,
  but do not retain invitation row-level before/after state.
- No PostgreSQL server was available in the local environment, so PostgreSQL
  migration execution, trigger behavior, concurrency, and production DB role
  privileges are not verified.
- The matrix deliberately classifies unsupported/out-of-process mutation
  channels instead of claiming universal audit coverage.

## Validation evidence

Final local run: `ZSH_ENV=test python manage.py test` passed 237 tests with
5 skips. Focused audit/append-only/invitation tests passed 35 tests with 2
skips. `manage.py check`, `makemigrations --check --dry-run`, Python
`compileall`, and `git diff --check` completed successfully. SQLite reports
the existing `PublicHoliday` `nulls_distinct` unsupported-constraint warning;
the skipped tests include backend-specific PostgreSQL checks. PostgreSQL
migration and trigger behavior remain NOT VERIFIED.
