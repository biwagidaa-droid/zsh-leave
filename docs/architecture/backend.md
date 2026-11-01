# Backend Architecture

## 1. Objective
The current backend is intentionally a thin Django application over a domain-first engine. The main business rules live under `backend/zsh_core`, while `backend/leave` contains the persistence, scaffolding, and service layer boundaries for leave operations.

## 2. Layering
- Presentation Layer: Django views, DRF endpoints, OpenAPI schema, UI-facing JSON responses.
- API Layer: REST API routes under `/api/v1/` and schema generation through drf-spectacular.
- Application / Service Layer: `backend/leave/services.py` and `backend/leave/admin_services.py` manage domain actions, validation, and audit logging.
- Domain Logic Layer: `backend/zsh_core/*.py` implements leave policy, balance, workday, holiday, permission, report, and workflow logic.
- Persistence Layer: Django ORM models in `backend/leave/models.py` and migrations in `backend/leave/migrations/`.
- Infrastructure Layer: `config/settings*.py`, `config/urls.py`, logging, database, and environment loading.
- Background Processing Layer: planned, not implemented in this mission; `BackgroundJob` is modeled as future work.
- Audit and Observability Layer: `AuditEvent`, `LeaveRequestEvent`, `PublicHolidayHistory`, and structured logging.

## 3. Module Responsibilities
- `backend/config`: environment and web configuration.
- `backend/leave/models.py`: persistent leave domain data model.
- `backend/leave/services.py`: business transaction entry points for leave request lifecycle.
- `backend/leave/admin_services.py`: configuration and holiday administration services.
- `backend/zsh_core`: pure domain logic with no framework dependency.
- `backend/tests`: executable validation for the core rules and runtime foundation.

## 4. Request Flow
1. HTTP request arrives at `config/urls.py`.
2. Route logic dispatches to a Django URL under `leave/urls.py`.
3. View or DRF endpoint validates access and returns an API response.
4. Service calls apply transactional domain rules.
5. Models persist data through Django ORM.
6. Audit events and request events are recorded for traceability.

## 5. Validation and Transactions
- Validation should occur as close as possible to service entry points.
- Database write operations are intentionally transaction-scoped inside service functions.
- Critical actions keep row-level locking (`select_for_update`) where concurrent changes are possible.
- The domain layer raises explicit errors rather than swallowing exceptions.

## 6. Error Handling
- Domain errors remain explicit and typed by the workflow layer.
- Service layer converts domain failures into stable API responses.
- Infrastructure errors are surfaced by health/readiness checks without leaking secrets.

## 7. Security and Observability
- `backend/leave/authorization.py` resolves server-side role, operation, organization-scope, queryset, and object-level permissions; frontend role metadata is not authoritative.
- Role grants and revocations are transactional, audited application services exposed only to system administrators.
- Environment variables carry secrets and configuration values.
- Secrets are never embedded in the repository.
- Logs are structured but intentionally avoid credentials, tokens, and medical details.

## 8. Future Scaling
This foundation supports later feature work such as the approval graph and complete reporting without forcing a rewrite of the domain engine. Session authentication and centralized RBAC are implemented; leave workflow APIs and broader account lifecycle remain future work.
