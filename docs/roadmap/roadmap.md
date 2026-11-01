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
- Scope: User lifecycle, roles, permissions, contracts, and approval flows.
- Status: Not Started
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
- Status: In Progress (date-conversion endpoint only)
- Completed in this increment: stateless Jalali/Gregorian conversion API with input validation and boundary tests.
- Remaining: authenticated organization-scoped calendar APIs, effective-dated work patterns, holiday management API/history, versioned leave policies, and production calendar UI integration.
- Dependencies: Phase 03 identity, permissions, and organization scope; operational Phase 04/05 services.

## Phase 07 – Jobs, Scheduler, and Notifications
- Goal: Deliver idempotent background execution and persistent notifications.
- Status: Blocked
- Dependencies: operational Phase 03 permissions, Phase 04 workflow and ledger services, and approved reminder/escalation/retention policies.

## Phase 08 – HR Operations and Analytics
- Goal: Deliver secure HR operations, employee records, imports, attachments, and analytics.
- Status: Blocked
- Dependencies: operational Phase 03 permissions and organization scope, Phase 04/05 APIs, and approved HR, data-retention, and sensitive-document policies.
