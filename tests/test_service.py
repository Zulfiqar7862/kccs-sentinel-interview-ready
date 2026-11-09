"""Application-service behaviour that is not visible through a single endpoint."""

from datetime import UTC

from conftest import FIXED_NOW, principal
from kccs_evidence.application.service import KernelService
from kccs_evidence.domain.obligations import IllegalTransition


def test_supersession_follows_insertion_order_not_hash_order(store, tmp_path):
    """Regression: with a fixed clock the 'previous' assessment used to be chosen by assessment_id (hash) order."""
    svc = KernelService(store, tmp_path, lambda: FIXED_NOW)
    p = principal("T-KAVERI")
    cutoffs = ["alert", "2026-08-15T00:00:00Z", "extract"]
    ids = [svc.assess(p, "T-KAVERI", "EXC-107133", knowledge_cutoff=c)[0]["assessment_id"] for c in cutoffs]
    hist = svc.assessment_history(p, "T-KAVERI", "EXC-107133")
    assert [h["assessment_id"] for h in hist] == ids
    assert [h["supersedes"] for h in hist] == [None, ids[0], ids[1]]


def test_obligation_ledger_is_rebuilt_from_the_transition_log(store, tmp_path):
    svc = KernelService(store, tmp_path, lambda: FIXED_NOW)
    p = principal("T-KAVERI")
    svc.transition_obligation(
        p,
        "T-KAVERI",
        "EXC-107133",
        to_state="SUBMISSION_QUEUED",
        expected_version=1,
        note="precautionary",
        idempotency_key=None,
    )
    rebuilt = KernelService(store, tmp_path, lambda: FIXED_NOW)
    ob = rebuilt.ledger.get("T-KAVERI", "EXC-107133")
    assert (ob.state, ob.version) == ("SUBMISSION_QUEUED", 2)
    assert ob.due_at is not None and ob.due_at.isoformat().startswith("2026-08-12T06:31")


def test_idempotency_key_cannot_be_reused_for_a_different_request(store, tmp_path):
    svc = KernelService(store, tmp_path, lambda: FIXED_NOW)
    p = principal("T-KAVERI")
    svc.transition_obligation(
        p,
        "T-KAVERI",
        "EXC-107133",
        to_state="NOTIFIABLE_CONFIRMED",
        expected_version=1,
        note="n",
        idempotency_key="key-1",
    )
    try:
        svc.transition_obligation(
            p,
            "T-KAVERI",
            "EXC-107133",
            to_state="SUBMISSION_QUEUED",
            expected_version=2,
            note="n",
            idempotency_key="key-1",
        )
        raise AssertionError("expected IllegalTransition")
    except IllegalTransition:
        pass


def test_readiness_detects_a_tampered_stored_assessment(store, tmp_path):
    svc = KernelService(store, tmp_path, lambda: FIXED_NOW)
    svc.assess(principal("T-KAVERI"), "T-KAVERI", "EXC-107133")
    assert svc.readiness()["ready"] is True
    store.raw_execute("DROP TRIGGER trg_assessment_no_update")
    store.raw_execute("UPDATE assessment SET payload_json = replace(payload_json, 'ABSTAIN', 'READY')")
    res = svc.readiness()
    assert res["ready"] is False and res["assessments_failing_hash"] and res["missing_triggers"]


def test_obligation_queue_never_shows_alerts_received_after_as_of(store, tmp_path):
    from datetime import datetime

    svc = KernelService(store, tmp_path, lambda: FIXED_NOW)
    as_of = datetime(2026, 7, 28, 6, 30, tzinfo=UTC)  # one minute before EXC-107133 reached Sentinel
    p = principal("T-KAVERI")
    before = svc.obligations(p, tenant="T-KAVERI", now=as_of, margin_hours=720, only_at_risk=False)
    assert all(o["clock_start_utc"] <= "2026-07-28T06:30:00Z" for o in before)
    assert "EXC-107133" not in {o["event_id"] for o in before}
    after = svc.obligations(
        p,
        tenant="T-KAVERI",
        now=as_of.replace(minute=32),
        margin_hours=720,
        only_at_risk=False,
        received_within_hours=1,
    )
    assert [o["event_id"] for o in after] == ["EXC-107133"]
