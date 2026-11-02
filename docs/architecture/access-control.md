# Access-Control Architecture

## 1. Enforcement Principle

The backend is the authorization authority. Frontend roles are navigation/display metadata only; API access is resolved from the authenticated Django user, current employee profile, active role assignments, and requested resource scope. No request payload role, company, employee, or scope is trusted to grant access.

## 2. Roles and Assignments

- **Employee:** derived from the user's active employee profile; personal access is limited to that profile.
- **Direct manager:** derived from current direct reports for team-level queries. Individual leave requests use their persisted `manager_snapshot`, so a later reporting-line change does not transfer an existing request to the new manager.
- **HR:** explicit active `RoleAssignment`; scope is global-denied and must identify a company, site, department, or employee.
- **System administrator:** global configuration and role-assignment management only. Django superusers remain trusted system operators. Neither administrator status nor executive status grants individual leave-record access.
- **Executive viewer:** explicit company/site/department-scoped assignment. Individual leave records are not exposed; aggregate reporting APIs are not yet implemented.

Assignments are persisted in `RoleAssignment`, reject invalid scope combinations and cross-company site/department/employee links, and are unique while active. Grants and revocations are performed through audited services; revocation is immediate and soft-deactivation preserves history. An administrator cannot grant or revoke their own assignment. Existing active superusers are migrated to global administrator assignments. Existing HR/Executive group membership is migrated only when it maps to an employee profile/company; unmappable memberships fail closed. Groups alone never grant application permissions.

## 3. Organization Scopes

Supported assignment scopes are global (system administrator only), company, site, department, and employee. HR querysets are constrained at the database layer to each assignment's selected scope. Employee and manager selectors include self and permitted team members. Executives and system administrators are excluded from individual leave selectors.

Organization Sites are company-owned siblings of Departments, not children of Departments. Company-scoped HR can manage Sites only within its assigned company; department- and site-scoped HR can read Sites visible in their scope but cannot mutate Site records. Site-scoped HR employee access is constrained by both company and Site. Site ownership is immutable after creation. Deactivation preserves existing employee and history references while preventing new employee assignments; physical deletion is permitted only when protected references do not exist.

## 4. Permission and Object Rules

`leave.authorization` is the shared permission engine and ORM selector layer. It resolves roles on each request (no long-lived role cache), checks operation permissions, and provides scoped employee/leave-request querysets plus object-level `can_view_leave_request` and `can_decide_leave_request` checks.

- Employees see their own individual leave data.
- Managers see requests addressed to their manager snapshot; manager decisions are limited to non-confidential requests and exclude their own requests.
- HR access is limited to assigned organization scope, including confidential leave details in object-level policy.
- Administrators may manage system configuration and assignments but cannot use those privileges to read or decide individual leave requests.
- Executives have no individual leave visibility.
- Out-of-scope employee selection and object lookup use a non-disclosing 404.

Existing API enforcement covers calendar events, workday estimates, effective work-pattern/policy reads, administrative configuration, and role assignment management at `/api/v1/admin/role-assignments/`. The existing leave application service also derives the actor role from the authorization context and loads requests through the scoped selector; it never accepts a caller-supplied role. Public leave workflow endpoints do not yet exist and must preserve these checks.

## 5. Verification

Policy and API tests exercise company/site/department/employee scope, cross-company filtering, stale manager snapshots, IDOR, role self-escalation, audited grant/revocation, administrator separation of duties, and confidential canary non-leakage. See `backend/tests/test_rbac.py` and `backend/leave/tests/test_calendar.py`.
