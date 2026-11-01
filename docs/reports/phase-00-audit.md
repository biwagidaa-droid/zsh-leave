# Phase 00 Audit Report

## A. Overall Status
- Repository structure: project is partitioned into `backend` and `frontend` with shared documentation under `docs`.
- Technologies: Python + Django + DRF + PostgreSQL target + React + Vite + TypeScript.
- Dependency versions:
  - Python: 3.14.2 in this environment
  - Django: 5.2.18 after installation
  - Node: 24.22.2
  - npm: 11.19.1
- Build state: frontend build is not yet validated in this mission; backend foundation is validated with Django tests.
- Test state: 107 backend tests pass with test environment configuration; earlier baseline failed because `openpyxl` was not installed.
- Backend status: domain engine and Django skeleton are present; runtime foundation needed environment-aware settings and endpoint scaffolding.
- Frontend status: present and functional enough to build, but not part of the backend-facility scope.
- Database state: PostgreSQL is the target database, with SQLite used as a safe test fallback for local validation.

## B. Technical Review
- What exists: leave models, workflow logic, policy engine, reports, balance computation, holiday handling, and a Django runtime scaffold.
- What is incomplete: environment settings, API endpoints, migrations and runtime config for a proper operational backend.
- What is wrong: single-file settings were not environment-aware, the API route layer had no public endpoints, and no migration state was tracked at the project level.
- What is duplicated or noisy: none beyond the tangential documentation and multiple architectural docs that were not yet organized under `docs/architecture`.
- What needs fixing: env-driven settings, migration generation, health/readiness API, proper documentation structure, dependency standardization.
- What requires organization decision: business policy values such as leave calendar and entitlement limits remain pending approval.

## C. Issue Registry
### P0-01: Missing backend runtime foundation
- File / path: `backend/config/settings.py`, `backend/config/urls.py`
- Description: settings and routes were not production-safe and no public API existed.
- Impact: deployment and validation were blocked.
- Remedy: environment-based settings and health/readiness endpoints.
- Dependency: runtime environment and Django config.
- Status: Resolved in Phase 02.

### P1-01: Missing dependency installation for export tests
- File / path: `backend/requirements.txt`, test execution logs
- Description: `openpyxl` was not installed despite being declared in requirements and required by exports tests.
- Impact: export tests failed before the backend runtime could be considered healthy.
- Remedy: install and validate the declared dependency set.
- Dependency: package installation and environment setup.
- Status: Resolved.

### P2-01: Environment configuration not standardized
- File / path: `.env.example` (new), `backend/config/settings*.py`
- Description: no template existed to standardize local runtime configuration.
- Impact: developers could not reproduce the same backend environment reliably.
- Remedy: add `.env.example` and environment-driven settings split by environment.
- Dependency: project startup instructions.
- Status: Resolved.

## D. Technical Debt
- business policy decisions remain remote and unapproved
- operational auth + RBAC are intentionally deferred
- the org model needs site/unit expansion and effective-dated transitions
- future attach/comment/background-job features remain outside the current scope

## E. Capability Matrix
| Capability | UI Implemented | Frontend Logic | Backend Implemented | DB Supported | API Integrated | Tested | Production Ready |
|---|---|---|---|---|---|---|---|
| Leave request flow | Partial | Partial | Partial | Partial | Planned | Partial | No |
| Balance / quota logic | Partial | Partial | Yes | Partial | Planned | Yes | No |
| Holidays & settings | Partial | Partial | Yes | Yes | Planned | Yes | No |
| Reporting | Partial | Partial | Partial | Partial | Planned | Partial | No |
| Bradford analytics | Partial | Partial | Partial | Partial | Planned | Partial | No |
| Audit trail | Partial | No | Yes | Yes | Planned | Partial | No |
| Authorization | No | No | No | Planned | No | No | No |

Note: the matrix reflects the actual state as seen in code and tests; it does not claim production readiness without evidence.
