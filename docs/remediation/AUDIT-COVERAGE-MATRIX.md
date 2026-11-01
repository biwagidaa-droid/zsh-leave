# Sensitive mutation audit coverage matrix

## Scope and evidence

This inventory covers the current Django API routes and mutation services under
`backend/leave`, including the requested employee, organization, role, leave,
entitlement, calendar, account-lifecycle, and audit-query paths. It is an
application-path inventory, not proof that arbitrary ORM, SQL, shell, or
future integration writes are audited. `AuditEvent` is append-only; high-risk
mutation services write it in their database transaction and fail closed if
the insert fails.

Snapshots are produced by `leave.audit_services` from per-entity allowlists.
Free-form Bradford note/comment/attachment names, emails, credentials, token
material, and leave request reason/comment text are not copied into audit
snapshots. HR audit queries are limited to currently scoped employees and
return identifiers/action/timestamp only; before/after, reasons, source, and
correlation IDs are restricted to global administrators.

| Entity | Operation / entry point | Actor types | Before state | After state | Audit event status | Missing coverage / qualification |
|---|---|---|---|---|---|---|
| EmployeeProfile | Create/update, `employees` API; employment access synchronization | Scoped HR, global admin; system-side account lifecycle | Update snapshot; none for create | Allowlisted profile/organization/status fields; display-name change flag only | Covered transactionally (`employee.create/update`) | Direct ORM/script writes are not intercepted. User name/email/password are deliberately omitted. |
| Employee account / invitation | Invite, resend, revoke, suspend, activation, offboarding | Scoped HR/admin; account owner/system for activation/offboarding | Not consistently available | Invitation row status/purpose/expiry or current profile status; no credential/token data | Action event retained; event insert is fail-closed in enclosing transaction where one exists | Some lifecycle event before states are unavailable. Some activation failure audits occur outside a mutation transaction by design. |
| User authentication | Login/logout/password change and authentication failure | Authenticated user/system; anonymous caller for failed attempts | None | None; only action/result and non-secret account identifier | Covered as authentication/security events | Authentication is not an HR entity mutation; password hashes and credentials are never snapshotted. Invalid-login events may use a username identifier and are visible only to global administrators. |
| Company | Create/update/active flag, `companies` API | Global admin | Full allowlisted state on update | Full allowlisted state | Covered transactionally (`company.create/update`) | No company delete route. Direct ORM writes are not intercepted. |
| Department | Create/update, `departments` API | Global admin | Full allowlisted state on update | Full allowlisted state | Covered transactionally (`department.create/update`) | No department delete route. |
| OrganizationSite | Create/update/active flag, `sites` API | Global admin | Full allowlisted state on update | Full allowlisted state | Covered transactionally (`organization_site.create/update`) | Route is backend-only; no Frontend changes were made. Direct ORM writes remain outside the audit boundary. |
| ContractPeriod | Create, `contracts` API | Scoped HR, global admin | None (create-only route) | Employee, dates, workdays, contract percentage | Covered transactionally (`contract_period.create`) | No update/delete API exists; any future one must add before/after audit. |
| BradfordNote | Create/update upsert, `bradford_notes` API | Scoped HR, global admin | Employee/author metadata only | Employee/author metadata plus `contentChanged` | Covered transactionally (`bradford_note.create/update`) | No delete API exists. Note text is intentionally not stored in `AuditEvent`. |
| LeaveType | Create/update/deactivate (`enabled=false`) | Global admin with `leave_type.global.manage` | Full allowlisted state | Full allowlisted state | Covered transactionally with required reason and correlation | DELETE/import/bulk routes are not supported. |
| RoleAssignment | Grant/revoke, role assignment service/API | Global admin | None for grant; complete assignment state for revoke | Complete assignment state | Covered transactionally (`role.assignment.granted/revoked`) | No physical-delete route; direct ORM writes do not produce AuditEvent. |
| WorkPattern | Create, `create_work_pattern` / calendar API | Global admin | None (create-only route) | Allowlisted schedule/scope/effective dates | Covered transactionally (`work_pattern.create`) | No update/delete API exists. Model-level direct writes are not audited. |
| LeavePolicyVersion | Create immutable version | Global admin | None (versioned append-only entity) | Scope, version, effective date, validated policy values | Covered transactionally (`leave_policy.create_version`) | Reason remains in policy version and audit event; arbitrary ORM inserts can bypass service-level audit. |
| LeaveRequest | Submit, correct, amend, decide, cancel, withdraw, HR absence, overdue escalation | Employee, manager, scoped HR, system job | Status or explicit correction snapshot | Status and allowlisted request fields; no free-text rationale | Covered with `LeaveRequestEvent` and `AuditEvent` in mutation transaction | Request body/reason text is excluded from AuditEvent; request event/comment services remain separate domain history. |
| LeaveRequestComment | Add comment | Request participant (employee, manager, scoped HR) | None (append-only) | Request and actor IDs only | Covered transactionally; body excluded | Comment content remains in its domain table and existing scoped API only. |
| LeaveRequestAttachment | Add attachment | Visible request participant | None | Request, uploader, content type, size; filename/file excluded | Covered transactionally | Storage object lifecycle is not a transactional database write; file cleanup/compensation is not included here. |
| LeaveEntitlement / EntitlementEvent | Opening entitlement, adjustment, rollover/reversal and request-ledger transitions | Scoped HR/admin, employee workflow actor, system | Ledger-derived before balance | Ledger-derived after balance, entitlement/employee/type/year IDs | Covered per ledger event and in the entitlement transaction | CSV import is one audited opening event per accepted row; no separate batch summary event. |
| Entitlement import | CSV bulk creation, `entitlement_import` | Scoped HR, global admin | None per new row | Per-row opening ledger state and target identifiers | Covered per record; all accepted rows are atomic | Current contract rejects a mixed-validity commit; preview is not a mutation. |
| SystemSetting | Change, `set_setting` | Global admin | Previous value | New validated value | Covered transactionally | Current schema settings are configuration, not credentials. |
| PublicHoliday / CalendarHoliday | Create/update/deactivate legacy or range-based holidays | Global admin | Before snapshot for updates/deactivation | After snapshot | Covered transactionally with history row | Legacy delete is logical deactivation. |
| AuditEvent | Read `/audit/events/` | Global admin; scoped HR | N/A | N/A | Append-only; ORM and database guards apply | Only administrators see snapshots/reasons/correlation/source. HR sees scoped, redacted event summaries; ordinary users are denied. |
| NotificationRead | Mark notification read | Authenticated recipient | N/A | N/A | Not audited | Operational acknowledgement state, not a business-critical HR/admin mutation. |

## Inventory limitations

- There are no Django admin registrations for these business models.
- Supported organization CRUD APIs are Company, Department, and the backend
  OrganizationSite routes. ContractPeriod is create-only; WorkPattern and
  LeavePolicyVersion are versioned/create-only; BradfordNote is upsert-only.
- This matrix does not certify external scripts, ad hoc ORM writes, raw SQL,
  database administrators, future endpoints, or unobserved background jobs.
- The production PostgreSQL database and privilege configuration were not
  available during local validation. Database triggers prevent UPDATE/DELETE,
  but INSERT privilege control remains a deployment responsibility.

## Audit write policy

Audit records are inserted using `record_audit` or `record_model_change`.
Mutation services wrap the business write and audit insert in `transaction.atomic`;
an audit database error therefore aborts both. Correlation IDs are validated
and propagated by `AuditContextMiddleware`; source context is server-derived
from the HTTP method and path. Actor identity is always taken from the
authenticated server-side user, never from request data.
