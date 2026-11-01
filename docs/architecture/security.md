# Security Architecture

## 1. Scope
This document captures the current backend posture and distinguishes the approved baseline from future implementation tasks.

## 2. Security Areas
- Authentication: Not yet operational; Phase 03 requirement.
- Authorization: Modeled but not enforced in code; Phase 03 requirement.
- CSRF: Enabled in Django settings; requires cookie and host policy review in production.
- CORS: Not yet configured explicitly; require approved frontend origin list in production.
- Rate Limiting: DRF throttle is configured at the framework level as a baseline.
- Secret Management: Environment variables only; no secrets committed to repo.
- Session Security: HttpOnly and SameSite are configured; secure cookies in non-debug mode.
- Password Security: Argon2 is preferred via `AUTH_PASSWORD_HASHERS`.
- Audit Logging: Request and audit event models exist for append-only traceability.
- Sensitive Data Redaction: logs should not capture tokens or medical details.
- File Security: attachment handling is not yet implemented; future media validation needed.
- SQL Injection: ORM usage reduces direct SQL risk; parameterized queries remain standard.
- XSS: template and output layers are not yet broad enough to warrant a full frontend risk review; future sanitization still needed.
- Input Validation: service and schema validation exist for settings and leave logic.
- Secure Headers: basic security flags are enabled in settings.
- Production Settings: require `DEBUG=False` and strict host configuration.
- Dependency Security: runtime dependencies must be reviewed during release.
- Backup Security: no operational backup policy documented yet.

## 3. Phase Allocation
- Phase 00-02: settings hardening, environment separation, health/readiness, structured logging, migration baseline
- Phase 03: authentication, authorization, session and user security
- Later phases: attachment handling, media validation, comprehensive audit and log retention policies
