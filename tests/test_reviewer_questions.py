"""The twelve reviewer questions (tab 10), one test per question the pack lets us answer.

Each test uses a real workbook event whose written override reason (tab 09) or brief narrative
names that concern, and checks that the kernel surfaces it with a named finding. Questions the
pack cannot answer (Q6 duplicate detection) are asserted as *absent* so a future claim fails loudly.
"""

import pytest

from conftest import clock, principal
from kccs_evidence.application.assessment import build_assessment


def _tenant_of(snapshot, event_id: str) -> str:
    return next(
        r.tenant_code for r in snapshot.records if r.sheet == "01_Excursion_Events" and r.record_key == event_id
    )


def _assess(store, snapshot, event_id: str, cutoff: str = "alert"):
    t = _tenant_of(snapshot, event_id)
    return build_assessment(store, principal(t), t, event_id, knowledge_cutoff=cutoff, clock=clock)


def _codes(a) -> set[str]:
    return {f["code"] for f in a["findings"]}


def test_q1_sop_revision_at_origin_and_destination(store, snapshot):
    a = _assess(store, snapshot, "EXC-107133")
    assert a["evidence"]["sop_origin"][0]["status"] == "CONFLICT_OVERLAPPING_REVISIONS"
    assert a["evidence"]["sop_destination"][0]["in_force"] == ["Rev 02", "Rev 03"]


def test_q3_lane_history_is_surfaced_for_repeated_lane_excursions(store, snapshot):
    assert "LANE_HISTORY_PRESENT" in _codes(_assess(store, snapshot, "EXC-110455"))


def test_q4_carrier_subsidiary_resolves_to_its_own_contract(store, snapshot):
    a = _assess(store, snapshot, "EXC-110581")
    assert a["entities"]["carrier"]["resolved_id"] == "CNT-2023-0441"  # the GmbH, not the Pvt Ltd parent


def test_q4_contract_without_cold_chain_clause_is_a_liability_finding(store, snapshot):
    assert "CONTRACT_NO_COLD_CHAIN_CLAUSE" in _codes(_assess(store, snapshot, "EXC-110518"))


def test_q5_gateway_gap_and_interpolation_are_flagged(store, snapshot):
    codes = _codes(_assess(store, snapshot, "EXC-110504"))
    assert {"GATEWAY_GAP_IN_WINDOW", "INTERPOLATED_READINGS"} <= codes


def test_q6_duplicate_physical_excursion_is_not_claimed(store, snapshot):
    # Out of scope by design (no physical-excursion key in the pack); make sure nothing pretends otherwise.
    assert not any("DUPLICATE" in c for c in _codes(_assess(store, snapshot, "EXC-110532")))


def test_q7_bms_room_alert_tenant_is_derived_not_native(store, snapshot):
    assert "BMS_TENANT_ATTRIBUTION_DERIVED" in _codes(_assess(store, snapshot, "EXC-110525"))


def test_q7_dock_door_alignment_is_unverified(store, snapshot):
    assert "DOCK_DOOR_ALIGNMENT_UNVERIFIED" in _codes(_assess(store, snapshot, "EXC-110469"))


def test_q8_batch_exposure_history_is_named_as_missing(store, snapshot):
    a = _assess(store, snapshot, "EXC-110441")
    assert "BATCH_EXPOSURE_HISTORY_UNAVAILABLE" in a["missing_inputs"]


def test_q9_signing_authority_comes_from_tenant_constraints(store, snapshot):
    kav = _assess(store, snapshot, "EXC-107133")["disposition_authority"]
    vir = _assess(store, snapshot, "EXC-110497")["disposition_authority"]
    assert kav["who_signs"] == "Site QA" and kav["dual_signature_required"] is False
    assert vir["dual_signature_required"] is True and vir["source"] == "12_Tenant_Constraints"


def test_q10_notification_deadline_and_market(store, snapshot):
    a = _assess(store, snapshot, "EXC-107133")
    n = a["notification_track"]
    assert n["due_at_utc"] == "2026-08-12T06:31:00Z" and n["regime"]["hours"] == 360
    assert n["independent_of_disposition"] is True and n["paused_by_evidence_waits"] is False
    assert n["notifiability"].startswith("UNDETERMINED")  # a human decides notifiability


@pytest.mark.parametrize("event_id", ["EXC-110574"])
def test_q2_refer_qa_is_not_an_allowance(store, snapshot, event_id):
    assert "PRODUCT_MASTER_ALLOWANCE_IS_REFER_QA" in _codes(_assess(store, snapshot, event_id))


def test_q2_freeze_below_zero_is_a_cold_excursion(store, snapshot):
    assert "COLD_EXCURSION" in _codes(_assess(store, snapshot, "EXC-110483"))


def test_q12_basis_is_reconstructible_from_the_manifest(store, snapshot):
    a = _assess(store, snapshot, "EXC-107133")
    m = a["manifest"]
    assert m["model"]["route"] == "NONE" and m["code_sha256"] and m["cited_source_versions"]
    assert {"sop_scope_rules.json", "reference_facts.json"} <= set(m["config"])
