# Access-Control Architecture

## 1. Design Principle
Access control is defined as a future-phase concern. The current mission documents the required model without implementing operational auth mechanisms.

## 2. Target Model
Role + Permission + Organization Scope

### Roles
- Employee
- Direct Manager
- HR
- System Administrator
- Executive / Management Viewer

## 3. Permission Matrix (Design Only)
| Role | View Scope | Create | Edit | Approve / Reject | Report Access | Confidential Data |
|---|---|---|---|---|---|---|
| Employee | own requests and own profile | own leave requests | own pending requests | n/a | limited personal view | no |
| Direct Manager | team requests | team requests | team requests in scope | yes within team | team summary | limited |
| HR | company scope | company-level admin actions | company-level policy metadata | yes | company reporting | yes, if needed |
| System Admin | full system | system setup | system config | n/a | full | yes |
| Executive Viewer | org-scoped summary | no | no | no | aggregated reporting | limited and approved |

## 4. Scope Dimensions
- Company scope
- Site scope
- Department scope
- Unit scope
- Personal scope

## 5. Implementation Note
The operational solution for authentication, session management, and permission enforcement is intentionally deferred to Phase 03. This mission only establishes the required model and governance constraints.
