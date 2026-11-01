# Phase 01 Architecture Report

## Summary
Phase 01 established the required architecture contract and separated the current work from future-phase decisions. The existing `zsh_core` domain engine remains the root of the business logic, while Django is treated as the runtime and persistence platform.

## Key Decisions
- Keep the core domain engine independent from web framework concerns.
- Keep a thin persistence and API layer in Django.
- Treat auth and authorization as Phase 03 work.
- Keep PostgreSQL as the target database and SQLite as an explicit test fallback.
- Require business-policy decisions to be approved before they affect core logic.

## Output Files
- `docs/architecture/backend.md`
- `docs/architecture/database.md`
- `docs/architecture/organization-model.md`
- `docs/architecture/access-control.md`
- `docs/architecture/security.md`
- `docs/architecture/business-decisions.md`
- `docs/api/api-contract.md`
