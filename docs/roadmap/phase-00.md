# Phase 00 – Audit and Stabilization

## Objective
Establish a trustworthy repository baseline and identify the minimum-risk path for the first implementation phases.

## Scope
- repository structure review
- dependency inspection
- local environment validation
- baseline tests execution
- issue and technical debt registration
- standardization of environment variables and runtime assumptions

## Outcomes
- repository was confirmed as a Django + DRF backend plus React + Vite frontend
- the core business rules were already implemented in `backend/zsh_core`
- the backend runtime scaffold was incomplete and required environment and API foundation work
- the missing `openpyxl` dependency was blocking the export/import tests

## Acceptance
- repository baseline documented
- tests executed with real output captured
- environment variables documented
- blocked gaps explicitly flagged instead of hidden
