# Security Architecture

## 1. Scope
This document captures the current backend posture and distinguishes the approved baseline from future implementation tasks.

## 2. Security Areas
- Authentication: Session login, logout, current-user, and password-change APIs are implemented. The API enforces CSRF on state-changing authentication requests, rotates session/CSRF keys at login, invalidates the session at logout, and throttles login attempts. Password reset/provisioning and complete authorization remain out of scope.
- Authorization: Endpoint-specific checks exist for the calendar foundation. The organization calendar currently requires Django group `HR` plus an employee profile and is restricted to that profile's company. This is not a complete RBAC or organization-scope implementation; Phase 03 remains required.
- CSRF: Enabled in Django settings; the SPA bootstraps a CSRF cookie through `/auth/me`. Production cross-origin deployments must configure `ZSH_CSRF_TRUSTED_ORIGINS` and retain HTTPS.
- CORS: Not yet configured explicitly; require approved frontend origin list in production.
- Rate Limiting: Login has an active DRF anonymous throttle of 5 attempts/minute per client IP. Production deployments should configure a shared cache backend for consistent multi-worker limits.
- Secret Management: Runtime secrets are expected from environment variables. A heuristic source scan was performed, but dedicated secret scanning and Git-history review are still unverified.
- Session Security: HttpOnly and SameSite are configured; secure cookies in non-debug mode.
- Password Security: Argon2 is the preferred hasher with PBKDF2 legacy verification and upgrade; password changes apply Django's configured validators.
- Audit Logging: Request and audit event models exist for append-only traceability.
- Sensitive Data Redaction: logs should not capture tokens or medical details.
- File Security: attachment handling is not yet implemented; future media validation needed.
- SQL Injection: ORM usage reduces direct SQL risk; parameterized queries remain standard.
- XSS: template and output layers are not yet broad enough to warrant a full frontend risk review; future sanitization still needed.
- Input Validation: service and schema validation exist for settings and leave logic.
- Secure Headers: basic security flags are enabled in settings.
- Production Settings: require `DEBUG=False`, a 50-character `ZSH_SECRET_KEY`, a non-empty `ZSH_ALLOWED_HOSTS`, and `ZSH_DB_PASSWORD`; HTTPS redirect, HSTS, and secure cookies are enabled.
- Dependency Security: runtime dependencies must be reviewed during release.
- Backup Security: no operational backup policy documented yet.

## 3. Phase Allocation
- Phase 00-02: settings hardening, environment separation, health/readiness, structured logging, migration baseline
- Phase B: authentication endpoints, CSRF/session lifecycle, password security, and frontend session integration
- Later authorization phase: RBAC, organization scopes, password reset/provisioning, and comprehensive audit retention
- Later phases: attachment handling, media validation, comprehensive audit and log retention policies
