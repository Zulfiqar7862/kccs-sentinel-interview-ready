# ADR 0007 — Abstain on conflict; half-open site-local date intervals

**Status:** Accepted.

## Context
- EXC-110490: an overlapping SOP revision.
- SOP-MER-5228 Rev 05 precedes Rev 04, so "highest revision wins" is wrong.
- `supersedes_text` is free text.
- 115 SOP hand-overs have `effective_to == next effective_from`.
- Two site timezones are wrong or suspect (`00!R31`).

## Decision
- **Intervals:** an SOP revision is in force on a **site-local** date `d` when `effective_from <= d < effective_to`. A blank end is open; a blank start is rejected (fail closed).
- **Overlaps:** two revisions in force on the same date give `CONFLICT_OVERLAPPING_REVISIONS` (blocking), naming both. EXC-107133 has SOP-KAV-9392 Rev 02 and Rev 03.
- **Untrusted timezones:** if the site's timezone is untrusted or unknown, every plausible local date between UTC−12 and UTC+14 is checked. If the selections differ, the result is `BOUNDARY_AMBIGUOUS`.
- **Stability admissibility checks:**
  - owner = tenant;
  - presentation match (pen vs vial);
  - readability;
  - study type.
- **Master vs study:** a product-master limit that conflicts with the study is `STABILITY_MASTER_VS_STUDY_CONFLICT`.
- **Firmware under-reporting** "up to 1.8 °C" is an interval [0, +1.8], not a fixed offset.

## Consequences
- All 420 events abstain in this pack: case-specific blockers on 412 at alert, and pack-wide gaps only on 8 (no telemetry series, no SOP content).
- This is the honest output for this data, not a defect. A green status is reachable only when evidence exists (`test_never_a_disposition_across_all_events`).

## Alternatives rejected
- **Latest or highest revision wins**, **ranking candidates**, **fuzzy matching:** each one hides a conflict that the reviewer must see.

## How we would know it was wrong
Abstention rates that stay high after curation. The per-tenant blocking-reason table in `evaluation_summary.md` is the work list for curation, not a failure rate.
