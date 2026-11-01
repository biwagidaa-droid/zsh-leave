import unittest
from zsh_core.workflow import *


def C(actor, **kw):
    return Context(actor=actor, **kw)


class WorkflowTests(unittest.TestCase):
    def test_initial_status(self):
        self.assertEqual(initial_status(C(EMPLOYEE)), PENDING)
        self.assertEqual(initial_status(C(EMPLOYEE, has_manager=False)), ESCALATED)
        self.assertEqual(initial_status(C(EMPLOYEE, manager_away=True)), ESCALATED)
        self.assertEqual(initial_status(C(EMPLOYEE, requires_approval=False)), APPROVED)
        self.assertEqual(initial_status(C(HR, confidential=True)), APPROVED)
        with self.assertRaises(PermissionDenied):
            initial_status(C(EMPLOYEE, confidential=True))

    def test_manager_approve_and_reject(self):
        self.assertEqual(transition(PENDING, "approve", C(MANAGER)), APPROVED)
        self.assertEqual(transition(PENDING, "reject", C(MANAGER, reason="کمبود نیرو")), REJECTED)

    def test_reject_requires_reason(self):
        for r in ("", "   "):
            with self.assertRaises(ValidationError):
                transition(PENDING, "reject", C(MANAGER, reason=r))

    def test_employee_cannot_decide(self):
        with self.assertRaises(PermissionDenied):
            transition(PENDING, "approve", C(EMPLOYEE))

    def test_manager_cannot_decide_escalated_or_confidential(self):
        with self.assertRaises(PermissionDenied):
            transition(ESCALATED, "approve", C(MANAGER))
        with self.assertRaises(PermissionDenied):
            transition(PENDING, "approve", C(MANAGER, confidential=True))
        self.assertEqual(transition(ESCALATED, "approve", C(HR)), APPROVED)

    def test_system_escalation_only_from_pending(self):
        self.assertEqual(transition(PENDING, "escalate", C(SYSTEM)), ESCALATED)
        with self.assertRaises(InvalidTransition):
            transition(APPROVED, "escalate", C(SYSTEM))
        with self.assertRaises(PermissionDenied):
            transition(PENDING, "escalate", C(MANAGER))

    def test_terminal_states_are_final(self):
        for st in (REJECTED, CANCELLED):
            for ev in ("approve", "reject", "cancel", "request_withdraw"):
                with self.assertRaises(InvalidTransition):
                    transition(st, ev, C(HR, reason="x"))

    def test_employee_cancel_only_before_approval(self):
        self.assertEqual(transition(PENDING, "cancel", C(EMPLOYEE)), CANCELLED)
        with self.assertRaises(InvalidTransition):
            transition(APPROVED, "cancel", C(EMPLOYEE))

    def test_withdrawal_flow(self):
        self.assertEqual(transition(APPROVED, "request_withdraw", C(EMPLOYEE)), WITHDRAWAL_PENDING)
        self.assertEqual(transition(WITHDRAWAL_PENDING, "approve_withdraw", C(MANAGER)), CANCELLED)
        self.assertEqual(transition(WITHDRAWAL_PENDING, "reject_withdraw", C(MANAGER, reason="نیاز کاری")), APPROVED)
        with self.assertRaises(ValidationError):
            transition(WITHDRAWAL_PENDING, "reject_withdraw", C(MANAGER))

    def test_withdraw_blocked_while_amendment_in_flight(self):
        with self.assertRaises(ConflictError):
            transition(APPROVED, "request_withdraw", C(EMPLOYEE, amendment_in_flight=True))

    def test_only_one_amendment_in_flight(self):
        can_start_amendment(APPROVED, C(EMPLOYEE))
        with self.assertRaises(ConflictError):
            can_start_amendment(APPROVED, C(EMPLOYEE, amendment_in_flight=True))
        with self.assertRaises(InvalidTransition):
            can_start_amendment(PENDING, C(EMPLOYEE))

    def test_amendment_resolution(self):
        self.assertEqual(resolve_amendment(APPROVED, True), (CANCELLED, APPROVED))
        self.assertEqual(resolve_amendment(APPROVED, False), (APPROVED, REJECTED))
        with self.assertRaises(InvalidTransition):
            resolve_amendment(WITHDRAWAL_PENDING, True)

    def test_hr_cancel_needs_reason_and_role(self):
        self.assertEqual(transition(APPROVED, "hr_cancel", C(HR, reason="ثبت اشتباه")), CANCELLED)
        with self.assertRaises(ValidationError):
            transition(APPROVED, "hr_cancel", C(HR))
        with self.assertRaises(PermissionDenied):
            transition(APPROVED, "hr_cancel", C(MANAGER, reason="x"))

    def test_unknown_event(self):
        with self.assertRaises(InvalidTransition):
            transition(PENDING, "bogus", C(HR))


if __name__ == "__main__":
    unittest.main()
