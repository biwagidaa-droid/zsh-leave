import datetime as dt
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase

from leave.entitlement_services import (
    EntitlementConflict,
    adjust_entitlement,
    approve_request,
    carry_forward,
    create_entitlement,
    entitlement_balance,
    expire_carry_over,
    reconcile_entitlement,
    reconcile_entitlements,
    release_request,
    reserve_request,
    reverse_event,
    reverse_request,
)
from leave.models import (
    Company,
    EntitlementEvent,
    EmployeeProfile,
    LeaveEntitlement,
    LeavePolicyVersion,
    LeaveRequest,
    LeaveType,
    WorkPattern,
)
from leave.services import apply_event, submit_request
from zsh_core import jalali, workflow as wf
from zsh_core.policy import leave_year_of
from zsh_core.settings_schema import build_policy

D = Decimal


class EntitlementLedgerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ledger-hr")
        self.company = Company.objects.create(code="LEDGER", name="Ledger")
        self.employee = EmployeeProfile.objects.create(
            user=self.user, company=self.company, personnel_code="L-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.manager_user = get_user_model().objects.create_user(username="ledger-manager")
        self.manager = EmployeeProfile.objects.create(
            user=self.manager_user, company=self.company, personnel_code="L-2",
            start_date=dt.date(2020, 1, 1),
        )
        self.employee.manager = self.manager
        self.employee.save(update_fields=["manager"])
        self.leave_type = LeaveType.objects.create(
            key="ledger-annual", label_fa="Annual", counts_against_balance=True,
        )
        self.day = dt.date(2026, 11, 2)
        self.year = leave_year_of(self.day, build_policy({}))
        self.entitlement = create_entitlement(
            employee=self.employee, leave_type=self.leave_type, year=self.year,
            base_days=D("20"), actor=self.user, reason="opening",
            idempotency_key="opening-1",
        )

    def request(self, *, start=None, end=None, days="2", status=wf.PENDING):
        start = start or self.day
        return LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=start,
            end_date=end or start,
            working_days=D(days),
            status=status,
        )

    def balance(self, entitlement):
        return entitlement_balance(LeaveEntitlement.objects.get(pk=entitlement.pk))

    def test_reservation_approval_reversal_and_replay_preserve_balances(self):
        request = self.request()
        reserve_request(request=request, actor=self.user, idempotency_key="reserve-1")
        reserve_request(request=request, actor=self.user, idempotency_key="reserve-1")
        self.assertEqual(self.balance(self.entitlement), {
            "total": D("20.0"), "used": D("0.0"), "reserved": D("2.0"),
            "remaining": D("20.0"), "available": D("18.0"),
        })

        request.status = wf.APPROVED
        request.save(update_fields=["status"])
        approve_request(request=request, actor=self.user, idempotency_key="approve-1")
        approve_request(request=request, actor=self.user, idempotency_key="approve-1")
        self.assertEqual(self.balance(self.entitlement)["reserved"], D("0.0"))
        self.assertEqual(self.balance(self.entitlement)["used"], D("2.0"))

        request.status = wf.WITHDRAWAL_PENDING
        request.save(update_fields=["status"])
        reverse_request(
            request=request, actor=self.user, reason="approved withdrawal",
            idempotency_key="withdraw-1",
        )
        request.status = wf.CANCELLED
        request.save(update_fields=["status"])
        balance = self.balance(self.entitlement)
        self.assertEqual((balance["used"], balance["reserved"], balance["available"]),
                         (D("0.0"), D("0.0"), D("20.0")))
        self.assertTrue(reconcile_entitlement(self.entitlement.pk)["ok"])

    def test_rejected_request_releases_its_reservation(self):
        request = self.request(days="1.5")
        reserve_request(request=request, idempotency_key="reserve-rejected")
        release_request(
            request=request, actor=self.user, reason="rejected",
            idempotency_key="release-rejected",
        )
        self.assertEqual(self.balance(self.entitlement)["reserved"], D("0.0"))
        self.assertEqual(self.balance(self.entitlement)["available"], D("20.0"))

    def test_workflow_approval_and_withdrawal_write_ledger_atomically(self):
        request = self.request()
        request.manager_snapshot = self.manager
        request.save(update_fields=["manager_snapshot"])
        reserve_request(request=request, idempotency_key="workflow-reservation")

        approved = apply_event(
            request_id=request.pk, user=self.manager_user, event="approve",
        )
        self.assertEqual(approved.status, wf.APPROVED)
        self.assertEqual(self.balance(self.entitlement)["used"], D("2.0"))
        self.assertEqual(self.balance(self.entitlement)["reserved"], D("0.0"))

        pending_withdrawal = apply_event(
            request_id=request.pk, user=self.user, event="request_withdraw",
        )
        self.assertEqual(pending_withdrawal.status, wf.WITHDRAWAL_PENDING)
        cancelled = apply_event(
            request_id=request.pk, user=self.manager_user, event="approve_withdraw",
        )
        self.assertEqual(cancelled.status, wf.CANCELLED)
        self.assertEqual(self.balance(self.entitlement)["used"], D("0.0"))
        self.assertTrue(reconcile_entitlement(self.entitlement.pk)["ok"])

    def test_submit_request_automatically_reserves_counted_entitlement(self):
        policy = LeavePolicyVersion.objects.create(
            scope="company", company=self.company, version=1,
            effective_from=self.day, values={"policy.leave_calendar": "jalali"},
            reason="ledger test", created_by=self.user,
        )
        WorkPattern.objects.create(
            name="Ledger test", company=self.company, working_weekdays=[self.day.weekday()],
            start_time=dt.time(9), end_time=dt.time(17),
            effective_from=self.day, created_by=self.user,
        )
        request = submit_request(
            user=self.user, employee=self.employee, leave_type=self.leave_type,
            start=self.day, end=self.day,
        )
        self.assertEqual(request.policy_version_id, policy.pk)
        self.assertEqual(request.status, wf.PENDING)
        self.assertEqual(self.balance(self.entitlement)["reserved"], D("1.0"))
        self.assertTrue(reconcile_entitlement(self.entitlement.pk)["ok"])

    def test_adjustment_carry_forward_and_expiration_are_journaled(self):
        adjust_entitlement(
            entitlement_id=self.entitlement.pk, component="manual_adjustment",
            delta="-1.5", actor=self.user, reason="correction", idempotency_key="adjust-1",
        )
        adjust_entitlement(
            entitlement_id=self.entitlement.pk, component="manual_adjustment",
            delta="-1.5", actor=self.user, reason="correction", idempotency_key="adjust-1",
        )
        self.assertEqual(self.balance(self.entitlement)["total"], D("18.5"))

        carry = carry_forward(
            previous_entitlement_id=self.entitlement.pk,
            next_year=self.year + 1,
            policy="capped",
            cap=D("4"),
            actor=self.user,
            reason="year-end",
            idempotency_key="carry-1",
        )
        carry = LeaveEntitlement.objects.get(pk=carry.pk)
        self.assertEqual(self.balance(carry)["total"], D("4.0"))
        expire_carry_over(
            entitlement_id=carry.pk, actor=self.user, reason="expiry",
            idempotency_key="expire-1",
        )
        self.assertEqual(self.balance(carry)["total"], D("0.0"))
        self.assertTrue(reconcile_entitlement(carry.pk)["ok"])

    def test_carry_forward_uses_only_unconsumed_available_balance(self):
        request = self.request(days="4")
        reserve_request(request=request, idempotency_key="reserve-before-rollover")
        target = carry_forward(
            previous_entitlement_id=self.entitlement.pk,
            next_year=self.year + 1,
            policy="unlimited",
            reason="year-end",
            idempotency_key="carry-reserved",
        )
        self.assertEqual(self.balance(target)["total"], D("16.0"))

    def test_reversal_is_idempotent_and_cannot_be_applied_twice(self):
        event = adjust_entitlement(
            entitlement_id=self.entitlement.pk, component="manual_adjustment",
            delta="1", actor=self.user, reason="correction", idempotency_key="adjust-reverse",
        )
        reversed_event = reverse_event(
            event_id=event.pk, actor=self.user, reason="undo", idempotency_key="undo-1",
        )
        replay = reverse_event(
            event_id=event.pk, actor=self.user, reason="undo", idempotency_key="undo-1",
        )
        self.assertEqual(reversed_event.pk, replay.pk)
        with self.assertRaises(EntitlementConflict):
            reverse_event(
                event_id=event.pk, actor=self.user, reason="undo again",
                idempotency_key="undo-2",
            )
        self.assertEqual(self.balance(self.entitlement)["total"], D("20.0"))

    def test_projection_writes_without_ledger_entries_are_rejected(self):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                LeaveEntitlement.objects.filter(pk=self.entitlement.pk).update(
                    base_days=D("19"),
                )
        row = LeaveEntitlement.objects.get(pk=self.entitlement.pk)
        row.base_days = D("19")
        with self.assertRaises(PermissionError):
            row.save()
        self.assertTrue(reconcile_entitlement(self.entitlement.pk)["ok"])
        with self.assertRaises(PermissionError):
            EntitlementEvent.objects.first().delete()

    def test_cross_year_request_allocations_sum_to_requested_days(self):
        first = jalali.to_gregorian(self.year, 12, 29)
        last = jalali.to_gregorian(self.year + 1, 1, 2)
        if not LeaveEntitlement.objects.filter(employee=self.employee, leave_type=self.leave_type,
                                               year=self.year + 1).exists():
            create_entitlement(
                employee=self.employee, leave_type=self.leave_type, year=self.year + 1,
                base_days="5", actor=self.user, reason="next year",
                idempotency_key="opening-next-year",
            )
        request = self.request(start=first, end=last, days="3")
        reserve_request(request=request, idempotency_key="reserve-cross-year")
        balances = [
            entitlement_balance(item)["reserved"]
            for item in LeaveEntitlement.objects.filter(
                employee=self.employee, leave_type=self.leave_type,
                year__in=[self.year, self.year + 1],
            )
        ]
        self.assertEqual(sum(balances), D("3.0"))


@skipUnless(connection.vendor == "postgresql", "Concurrency guarantees require PostgreSQL")
class PostgreSQLEntitlementConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="ledger-concurrency")
        company = Company.objects.create(code="PGLEDGER", name="Ledger")
        self.employee = EmployeeProfile.objects.create(
            user=self.user, company=company, personnel_code="PG-1",
            start_date=dt.date(2020, 1, 1),
        )
        self.leave_type = LeaveType.objects.create(
            key="pg-ledger", label_fa="Annual", counts_against_balance=True,
        )
        self.day = dt.date(2026, 11, 2)
        self.year = leave_year_of(self.day, build_policy({}))
        self.entitlement = create_entitlement(
            employee=self.employee, leave_type=self.leave_type, year=self.year,
            base_days="20", actor=self.user, reason="opening",
            idempotency_key="pg-opening",
        )

    def _thread_reserve(self, request_id, key, barrier):
        close_old_connections()
        try:
            request = LeaveRequest.objects.get(pk=request_id)
            barrier.wait(timeout=10)
            reserve_request(request=request, idempotency_key=key)
            return True
        finally:
            close_old_connections()

    def test_parallel_reservations_serialize_without_lost_ledger_entries(self):
        requests = [
            LeaveRequest.objects.create(
                employee=self.employee, leave_type=self.leave_type,
                start_date=self.day, end_date=self.day,
                working_days=D("3"), status=wf.PENDING,
            )
            for _ in range(2)
        ]
        barrier = Barrier(2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda item: self._thread_reserve(item.pk, f"pg-reserve-{item.pk}", barrier),
                requests,
            ))
        self.assertEqual(results, [True, True])
        entitlement = LeaveEntitlement.objects.get(pk=self.entitlement.pk)
        self.assertEqual(entitlement_balance(entitlement)["reserved"], D("6.0"))
        self.assertEqual(
            EntitlementEvent.objects.filter(kind="reservation", request__in=requests).count(), 2,
        )

    def test_parallel_approval_replays_one_atomic_posting(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=self.day, end_date=self.day,
            working_days=D("2"), status=wf.PENDING,
        )
        reserve_request(request=request, idempotency_key="pg-approval-reserve")
        barrier = Barrier(2)

        def approve():
            close_old_connections()
            try:
                row = LeaveRequest.objects.get(pk=request.pk)
                barrier.wait(timeout=10)
                approve_request(
                    request=row, idempotency_key="pg-approval-once",
                )
                return True
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _: approve(), range(2))), [True, True])
        entitlement = LeaveEntitlement.objects.get(pk=self.entitlement.pk)
        balance = entitlement_balance(entitlement)
        self.assertEqual((balance["reserved"], balance["used"]), (D("0.0"), D("2.0")))
        self.assertEqual(
            EntitlementEvent.objects.filter(kind="approval", request=request).count(), 1,
        )

    def test_database_trigger_rejects_journal_updates(self):
        event = EntitlementEvent.objects.get(kind="opening")
        with self.assertRaises(DatabaseError):
            EntitlementEvent.objects.filter(pk=event.pk).update(reason="tampered")
