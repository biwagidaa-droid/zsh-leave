# Phase 01 – Architecture and Policy Definition

## Objective
Define the technical architecture, governance decisions, and system boundaries before adding operational features.

## Scope
- backend architecture document
- database architecture and ERD
- organizational model and scope boundaries
- business decision matrix
- access-control model
- API contract extraction
- security architecture baseline

## Outcomes
- the actual system is modeled as a layered Django project with a pure domain engine under `backend/zsh_core`
- future security and authorization are scoped as Phase 03 work and not prematurely implemented
- the API contract remains aligned with the current frontend and documents which endpoints are implemented versus planned

## Acceptance
- architecture and policy docs exist under `docs/architecture` and `docs/api`
- major decisions are marked as approved or pending organization confirmation
- future-phase dependencies are explicit and separated from the current scope
