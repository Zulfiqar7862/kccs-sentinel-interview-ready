"""KCCS Sentinel evidence-resolution and replay kernel (case-study prototype).

The kernel assembles an admissible, tenant-scoped, temporally explicit evidence
basis for a human QA decision. It never issues a pharmaceutical disposition.
"""

__version__ = "0.2.0"
RULESET_VERSION = "evidence-rules/0.1.0"
ASSESSMENT_SCHEMA_VERSION = "assessment/1.0"
STORE_SCHEMA_VERSION = 2  # v2 adds obligation_transition
