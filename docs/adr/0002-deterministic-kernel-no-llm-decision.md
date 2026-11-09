# ADR 0002 — Deterministic evidence kernel; no language model in any decision

**Status:** Accepted.

## Context
- Dr Rao's condition (brief §6): automation on closures only, never on decisions, and a replay on past cases before every change.
- Three incidents count against model-centred designs:
  - INC-2411: a prompt change silently moved recommendations for 31 customers.
  - INC-2509: model sunset.
  - The January pilot.
- The brief itself (§2): "The decisions are mostly not hard. Assembling enough evidence to be allowed to make them is the whole cost."
- Six tenants prohibit model APIs, and T-VIRENT is India-only (`12`). Self-hosting is $4,139 a month for one always-on g5.12xlarge, which is above the whole model budget.

## Decision
- The kernel is plain Python rules over versioned evidence. It never outputs a disposition: `is_disposition` is always `false`.
- Its output is one of two things:
  - `READY_FOR_QA_REVIEW`;
  - `ABSTAIN_BLOCKING_EVIDENCE_GAPS`, with named findings and required human actions.
- Every manifest records `model: NONE`.
- A language model is allowed later only as an optional **drafting** step whose only input is the assessment JSON. It must be removable with no loss of function.

## Consequences
- The same input always gives the same output and the same ID. Replay is exact, so Dr Rao's "show me where it would decide differently" is a diff of IDs and findings.
- Six of the 24 override reasons are out of scope because the pack lacks the data (`evidence/results/evaluation_summary.md`). A model could not fix that either.
- The "no LLM" route is always qualified, so a model sunset cannot stop the system.

## Alternatives rejected
- **A better recommendation prompt:** that was INC-2411.
- **A classifier trained on past dispositions:** past outcomes are not ground truth (EXC-110448 reasoning was wrong), and training across tenants breaks Meridian Cl.22.

## How we would know it was wrong
Reviewers would still spend most of their time on prose or judgement rather than on evidence lookup, measured by time per wait state. Then the drafting step earns its place. It still would not decide.
