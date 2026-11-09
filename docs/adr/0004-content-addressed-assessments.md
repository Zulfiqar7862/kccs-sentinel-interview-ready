# ADR 0004 — Content-addressed assessments; fingerprint excludes the interfaces layer

**Status:** Accepted.

## Context
- Board commitment #3: the full basis of any disposition within the hour, for 7 years.
- de Vries (Aurastat): "which version produced a given recommendation?"
- INC-2411 changed behaviour without anyone noticing.

## Decision
- `assessment_id = "ASM-" + sha256(canonical JSON of the payload)[:24]`.
- The payload includes the **manifest**:
  - kernel and ruleset versions;
  - the sha256 of every config file;
  - the cited source-record versions;
  - the model route (`NONE`);
  - `code_sha256`, the hash of every `.py` file under `domain/`, `application/`, `infrastructure/` and `config/`, plus the package `__init__.py`.
- `interfaces/` (CLI, API, web UI) is deliberately **not** fingerprinted, so a UI fix does not change assessment IDs. `test_fingerprint_excludes_interfaces_but_covers_rules` enforces this.
- Storing an identical assessment is a no-op. The API returns 200 instead of 201.
- A different assessment for the same event records `supersedes` and a `change_from_superseded` diff.
- Supersession follows insertion order (`first_stored_at, rowid`), not hash order. This was a real bug, fixed and covered by a regression test.

## Consequences
- Any change to a rule, config or adapter changes every ID it touches. That is the replay gate: before a release, compare the IDs and findings per tenant and name every tenant whose diff is non-empty.
- IDs differ between code versions. Documents quote IDs together with the commit that produced them.

## Alternatives rejected
- **Random UUIDs:** no proof of sameness.
- **A git SHA in the manifest only:** it misses uncommitted changes and config files.

## How we would know it was wrong
A harmless refactor would change every ID and make the replay diff noisy. Mitigation: the diff compares findings and status, not only IDs.
