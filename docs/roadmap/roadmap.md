# ZSH Leave Roadmap

Status legend: Not Started, In Progress, Blocked, Completed, Needs Review.

## Phase 00 – Audit and Stabilization
- Goal: Establish the actual repository baseline, dependency health, and operational risk state.
- Scope: repository audit, dependency validation, environment hygiene, test baseline, and issue logging.
- Status: Completed
- Deliverables: audit report, issue registry, technical debt log, and initial environment standardization.
- Acceptance: repository status recorded, baseline tests executed, and environment assumptions documented.

## Phase 01 – Architecture and Policy Definition
- Goal: Define the backend architecture, data model expectations, and governance decisions required before implementation.
- Scope: backend architecture, database model blueprint, organization model, business decision matrix, access-control design, API contract, security standard.
- Status: Completed
- Deliverables: architecture and design docs under docs/architecture and docs/api.
- Acceptance: architecture matches the actual backend skeleton and leaves future phases with explicit dependencies.

## Phase 02 – Backend and Database Foundation
- Goal: Prepare the working backend runtime, database configuration, migrations, and core API foundation.
- Scope: Django settings separation, PostgreSQL-ready config, migration generation, health/readiness API, observability/logging baseline.
- Status: Completed
- Deliverables: environment settings, migration, health APIs, and validation tests.
- Acceptance: backend configuration loads cleanly in test mode and the relevant regression suite passes.

## Phase 03 – Operational Authentication and Authorization
- Goal: Implement real identity, RBAC, and organizational policy enforcement.
- Scope: Session authentication, centralized RBAC, organization scopes, and user lifecycle administration.
- Status: In Progress (Phase B authentication and Phase C centralized RBAC complete; operational leave API authorization remains dependent on Phase 04)
- Phase C deliverables: persisted/audited role assignments, scoped permission engine and ORM selectors, object-level leave policies, role-management API, and adversarial policy/API tests.
- Dependencies: Phase 02 foundation, approved business policy decisions, HR migration data.

## Phase 04 – Core HR and Leave Operations
- Goal: Implement operational leave workflows beyond the foundation layer.
- Scope: requests, approvals, balance, policy engine, notifications, attachments, comments.
- Status: Not Started
- Dependencies: Phase 03 authentication and authorization.

## Phase 05 – Reporting and Analytics
- Goal: Deliver manager and HR reporting, Bradford analysis, and export features.
- Status: Not Started
- Dependencies: operational leave workflow and data model completion.

## Phase 06 – Calendar, Holidays, and Leave Policies
- Goal: Provide one trustworthy calendar conversion and business-day foundation for operational leave workflows.
- Status: In Progress (partial; not production-ready)
- Completed in this increment: authenticated calendar/holiday/day-estimate APIs; effective-dated Work Pattern and immutable Policy models/services; holiday audit history; daily leave submission uses backend workday calculation and policy snapshot; calendar UI reads event/holiday APIs in HTTP mode.
- Remaining: management UI for policy/work patterns/range holidays, backend hourly calculations, configurable leave-year/rollover/expiry, PostgreSQL and end-to-end verification.
- Dependencies: approved organization roles and HR policy decisions; actual company/site work schedules and official holiday sources.

## Phase 07 – Jobs, Scheduler, and Notifications
- Goal: Deliver idempotent background execution and persistent notifications.
- Status: Blocked
- Dependencies: Phase 06 acceptance, operational Phase 03 permissions, Phase 04 workflow and ledger services, and approved reminder/escalation/retention policies.

## Phase 08 – HR Operations and Analytics
- Goal: Deliver secure HR operations, employee records, imports, attachments, and analytics.
- Status: Blocked
- Dependencies: Phase 06/07 acceptance, operational Phase 03 permissions and organization scope, Phase 04/05 APIs, and approved HR, data-retention, and sensitive-document policies.

## Phase 09 – Management Dashboards and Reports
- Goal: Deliver real, permission-scoped operational dashboards and reports.
- Status: Blocked (initial audit: operational identity, leave ledger, organization scope, and reporting APIs are missing).
- Evidence: `docs/reports/phase-09-report.md`.

## Phase 10 – Frontend and User Experience
- Goal: Connect operational pages to real APIs and complete accessible, responsive workflows.
- Status: Partial (Demo is development-only and selected error fallbacks were removed; full API integration and E2E remain blocked).
- Evidence: `docs/reports/phase-10-report.md`.

## Phase 11 – Security, Verification, and Operations
- Goal: Verify authorization, data integrity, recovery, observability, and deployment readiness.
- Status: Partial / Not Ready (one calendar access-control defect fixed; full API, PostgreSQL, backup/restore, and deployment verification remain outstanding).
- Evidence: `docs/reports/phase-11-report.md` and `docs/reports/release-readiness-report.md`.
