import datetime as dt
import json
import unittest
from zsh_core.permissions import *

d = dt.date
SETTINGS = {}
CANARY = ("CANARY_TYPE", "CANARY_LABEL", "CANARY_REASON", "CANARY_COMMENT")


def facts(confidential=False, **kw):
    base = dict(id=1, employee_id=10, company_id=1, manager_snapshot_id=20, confidential=confidential,
                status="APPROVED", start=d(2026, 11, 1), end=d(2026, 11, 3),
                type_key=CANARY[0] if confidential else "annual",
                type_label=CANARY[1] if confidential else "استحقاقی",
                reason=CANARY[2] if confidential else "سفر", decision_comment=CANARY[3] if confidential else "ok",
                replacement_id=30, working_days="3")
    base.update(kw)
    return RequestFacts(**base)


OWNER = Viewer(1, frozenset({EMPLOYEE}), employee_id=10)
MANAGER_V = Viewer(2, frozenset({EMPLOYEE, MANAGER}), employee_id=20)
PEER = Viewer(3, frozenset({EMPLOYEE}), employee_id=11)
REPLACEMENT = Viewer(4, frozenset({EMPLOYEE}), employee_id=30)
OTHER_MANAGER = Viewer(5, frozenset({EMPLOYEE, MANAGER}), employee_id=21)
HR_ALL = Viewer(6, frozenset({EMPLOYEE, HR}), employee_id=40, hr_company_ids=None)
HR_C1 = Viewer(7, frozenset({HR}), employee_id=41, hr_company_ids=frozenset({1}))
HR_C2 = Viewer(8, frozenset({HR}), employee_id=42, hr_company_ids=frozenset({2}))
ADMIN_V = Viewer(9, frozenset({ADMIN}))
EXEC_V = Viewer(10, frozenset({EXEC}))
NON_HR = [OWNER, MANAGER_V, PEER, REPLACEMENT, OTHER_MANAGER, HR_C2, ADMIN_V, EXEC_V]


class AccessTests(unittest.TestCase):
    def test_view_matrix_normal_request(self):
        f = facts()
        expect = {OWNER: True, MANAGER_V: True, PEER: False, REPLACEMENT: False, OTHER_MANAGER: False,
                  HR_ALL: True, HR_C1: True, HR_C2: False, ADMIN_V: False, EXEC_V: False}
        for v, ok in expect.items():
            self.assertEqual(can_view_request(v, f), ok, v.user_id)
            self.assertEqual(serialize_request(v, f, SETTINGS) is not None, ok, v.user_id)   # IDOR → None

    def test_decide_matrix(self):
        f = facts()
        self.assertTrue(can_decide(MANAGER_V, f))
        self.assertTrue(can_decide(HR_C1, f))
        for v in (OWNER, PEER, OTHER_MANAGER, HR_C2, ADMIN_V, EXEC_V):
            self.assertFalse(can_decide(v, f), v.user_id)

    def test_manager_cannot_decide_own_request_or_confidential(self):
        self.assertFalse(can_decide(MANAGER_V, facts(employee_id=20)))
        self.assertFalse(can_decide(MANAGER_V, facts(confidential=True)))
        self.assertTrue(can_decide(HR_C1, facts(confidential=True)))

    def test_hr_scope_by_company(self):
        f = facts(company_id=2)
        self.assertFalse(can_view_request(HR_C1, f))
        self.assertTrue(can_view_request(HR_C2, f))
        self.assertTrue(can_view_request(HR_ALL, f))

    def test_role_without_hr_group_is_not_hr(self):
        v = Viewer(11, frozenset({EMPLOYEE}), employee_id=50, hr_company_ids=None)
        self.assertFalse(v.is_hr_for(1))


class ConfidentialityTests(unittest.TestCase):
    def test_hr_sees_everything(self):
        out = serialize_request(HR_C1, facts(True), SETTINGS)
        self.assertEqual(out["type"], CANARY[0])
        self.assertEqual(out["reason"], CANARY[2])

    def test_owner_and_manager_see_only_neutral(self):
        for v in (OWNER, MANAGER_V):
            out = serialize_request(v, facts(True), SETTINGS)
            self.assertIsNone(out["type"])
            self.assertIsNone(out["reason"])
            self.assertEqual(out["typeLabel"], NEUTRAL_LABEL)
            self.assertFalse(out["canDecide"])
            self.assertEqual(out["start"], "2026-11-01")     # بود و نبود غیبت پنهان نیست

    def test_owner_setting_reveals_type_only_never_reason(self):
        out = serialize_request(OWNER, facts(True), {"privacy.employee_sees_own_confidential_type": True})
        self.assertEqual(out["type"], CANARY[0])
        self.assertIsNone(out["reason"])
        self.assertIsNone(out["decisionComment"])
        mgr = serialize_request(MANAGER_V, facts(True), {"privacy.employee_sees_own_confidential_type": True})
        self.assertIsNone(mgr["type"])             # فقط خود کارمند، نه مدیر

    def test_canary_never_leaks_to_non_authorized(self):
        f = facts(True)
        for v in NON_HR:
            blobs = [serialize_request(v, f, SETTINGS), calendar_event(v, f, SETTINGS)]
            for ev in ("submitted", "approved", "rejected", "escalated", "cancelled",
                       "replacement_assigned", "replacement_cancelled", "unknown"):
                blobs.append(notification_text(ev, f, v))
            dumped = json.dumps(blobs, ensure_ascii=False, default=str)
            for c in CANARY:
                self.assertNotIn(c, dumped, f"نشت {c} به کاربر {v.user_id}")

    def test_canary_leak_even_with_reveal_settings_on(self):
        s = {"privacy.peers_see_leave_type": True}
        for v in (PEER, MANAGER_V, ADMIN_V, EXEC_V, HR_C2):
            dumped = json.dumps(calendar_event(v, facts(True), s), ensure_ascii=False)
            self.assertNotIn(CANARY[1], dumped)

    def test_calendar_labels_normal_type(self):
        f = facts()
        self.assertEqual(calendar_event(PEER, f, SETTINGS)["label"], NEUTRAL_LABEL)
        self.assertEqual(calendar_event(MANAGER_V, f, SETTINGS)["label"], "استحقاقی")
        self.assertEqual(calendar_event(HR_C1, f, SETTINGS)["label"], "استحقاقی")
        self.assertEqual(calendar_event(PEER, f, {"privacy.peers_see_leave_type": True})["label"], "استحقاقی")

    def test_hr_sees_confidential_label_in_calendar(self):
        self.assertEqual(calendar_event(HR_C1, facts(True), SETTINGS)["label"], CANARY[1])

    def test_notification_never_includes_reason_to_replacement(self):
        f = facts(reason="بیماری خاص")
        txt = notification_text("replacement_assigned", f, REPLACEMENT)
        self.assertNotIn("بیماری", txt)
        self.assertNotIn("2026", txt)

    def test_balance_type_names_hidden_from_non_hr(self):
        types = [{"key": "annual", "confidential": False}, {"key": "CANARY_TYPE", "confidential": True}]
        self.assertEqual([t["key"] for t in visible_balance_types(OWNER, 1, types)], ["annual"])
        self.assertEqual(len(visible_balance_types(HR_C1, 1, types)), 2)
        self.assertEqual(len(visible_balance_types(HR_C2, 1, types)), 1)


if __name__ == "__main__":
    unittest.main()
