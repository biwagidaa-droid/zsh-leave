# Business Decision Matrix

| Topic | Current Value | Proposed / Observed | Status | Decision Owner | Technical Impact |
|---|---|---|---|---|---|
| Leave calendar basis | Jalali | Jalali by default | Approved by implementation default | HR / Management | impacts holiday and entitlement calculations |
| Annual leave basis | monthly accrual pattern | configured through system settings | Needs review | HR | business policy engine |
| Sick leave policy | not final | default values are structural placeholders | Needs review | HR | affects entitlement and policy validation |
| Carry-over policy | supported by policy engine | explicit business rule required | Needs review | HR | balance logic |
| Maximum carry-over | not finalized | must be configured per policy | Needs review | HR | budget / entitlement |
| Hourly leave support | domain support exists but not fully operationalized | design pending | Needs review | HR + Product | require date/time semantics |
| Past-dated requests | controlled by policy | explicit allow/deny path | Needs review | HR | request validation |
| Overdue escalation | workflow layer has escalation concept | depends on policy settings | Needs review | Management | approval queue |
| Manager substitution | model supports `manager_snapshot` | not fully operationalized | Needs review | HR | approval chains |
| HR escalation | model supports direct manager and HR roles | not yet enforced | Needs review | Security / HR | access boundaries |
| Employees without direct manager | model supports null manager | requires policy | Needs review | HR | approval determination |
| Confidentiality | leave type can be marked confidential | access policy pending | Needs review | Security / HR | data visibility |
| Data retention | not finalized | depends on legal policy | Blocked | Legal / Security | audit retention |
| Holiday source | manual | manual by design | Approved by architecture | Admin | holiday configuration |
| Company work patterns | not normalized | future site / department schedule config required | Needs review | Management | staffing and leave patterns |
| Management access | not implemented | role model required | Needs review | IT Governance | permission model |

The current value column records the implemented or default state, while the proposed value is the business decision still waiting for explicit approval.
