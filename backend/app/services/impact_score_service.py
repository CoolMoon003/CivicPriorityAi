"""
Impact-score accessor for downstream consumers (currently: the 0/1
budget optimizer).

This module intentionally does NOT recompute priority/impact. The
project's existing ``PriorityEngine`` (see
``backend/app/scoring/priority_engine.py``) already produces a single
weighted 0-100 score per complaint at submission time, combining:

  * damage severity (35%)
  * model confidence (10%)
  * road importance (20%)
  * nearby-facility exposure (15%)
  * complaint recurrence (15%)
  * district safety context (5%)

That weighted score — stored as ``Complaint.priority_score`` — is
already exactly "how much civic good does repairing this do", which
is the same quantity a budget optimizer needs as its "impact" term.
So rather than inventing a second, parallel impact metric, this
service simply exposes ``Complaint.priority_score`` under the name
`impact_score`, with the mapping documented here in one place instead
of being re-derived (or silently duplicated) wherever it's needed.

If a genuinely distinct impact metric is introduced later (e.g. one
that also accounts for repeated post-repair failure), it should be
computed here and this docstring/mapping updated accordingly — the
optimizer itself only depends on this function's return value, not on
where the number comes from.
"""

from __future__ import annotations

from backend.app.models.complaint import Complaint


def get_impact_score(complaint: Complaint) -> float | None:
    """
    Return the impact score to use for optimization purposes.

    Mapping (documented, not fabricated):
        impact_score := complaint.priority_score

    Returns None if the complaint has no priority_score yet (e.g. a
    text/GPS-only complaint that never got a damage-detection pass) —
    callers must treat that as "impact unknown", never as zero.
    """

    if complaint.priority_score is None:
        return None

    return float(complaint.priority_score)
