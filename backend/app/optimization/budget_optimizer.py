"""
Budget-constrained repair portfolio optimizer.

TASK 9 — 0/1 KNAPSACK REPAIR OPTIMIZER
=======================================

This module answers the question the priority engine deliberately does
NOT answer: "given a fixed repair budget, which subset of already
-scored complaints should actually be repaired to maximize total
civic impact?"

It does NOT recompute or replace priority/impact scores (see
``backend/app/scoring/priority_engine.py`` and
``backend/app/services/impact_score_service.py``). It only consumes
those existing numbers, plus a repair cost per complaint, and solves:

    maximize   sum(impact_i * x_i)
    subject to sum(cost_i   * x_i) <= budget
               x_i in {0, 1}

This is the classic 0/1 knapsack problem, solved here with dynamic
programming (NOT sorting/greedy). Greedy-by-impact or
greedy-by-impact/cost-ratio approaches can both be beaten by a
combination of lower-impact-but-cheaper items that fit the budget
better — see ``test_budget_optimizer.py`` for a worked, deterministic
proof of this using the mentor-supplied example numbers.

COST HANDLING
-------------
This module never invents a cost for a complaint that already has a
verified ``Repair.repair_cost`` in the database. It only estimates a
cost when none exists yet (i.e. the complaint has not been repaired),
via ``estimate_repair_cost()`` below. That estimate is:

  * deterministic (same inputs -> same output, no randomness),
  * built only from information already in this project
    (YOLO damage type, severity, and road importance class — the same
    road-importance table already used by ``PriorityEngine``), and
  * always reported back with ``"cost_is_estimated": true`` so callers
    never mistake it for a verified/actual cost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.app.scoring.priority_engine import PriorityEngine


# --------------------------------------------------------------------
# 1. Repair candidate representation
# --------------------------------------------------------------------

@dataclass
class RepairCandidate:
    """
    One item eligible for the knapsack.

    ``impact_score`` and ``estimated_cost`` are the two values the
    optimizer actually uses. Everything else is carried through purely
    for reporting in the API response.
    """

    complaint_id: int
    impact_score: float
    estimated_cost: float
    cost_is_estimated: bool
    priority_level: str | None = None
    damage_type: str | None = None
    severity: str | None = None
    cost_note: str | None = field(default=None, repr=False)
    confidence: float | None = None
    detection_state: str | None = None


# --------------------------------------------------------------------
# 2. Deterministic ESTIMATED repair cost helper
# --------------------------------------------------------------------

# Base cost (INR) per YOLO/RDD2022 damage class, before severity/road
# multipliers. Order-of-magnitude figures only — NOT sourced from
# CPWD or any real cost schedule (explicitly out of scope for this
# task). Both the RDD2022 class codes and the human-readable labels
# the detector may emit are covered so this stays correct regardless
# of which form `Complaint.damage_type` is stored in.
_BASE_COST_BY_DAMAGE_TYPE = {
    "d00": 8_000.0,               # longitudinal crack
    "longitudinal crack": 8_000.0,
    "longitudinal_crack": 8_000.0,
    "d10": 9_000.0,                # transverse crack
    "transverse crack": 9_000.0,
    "transverse_crack": 9_000.0,
    "d20": 25_000.0,                # alligator crack
    "alligator crack": 25_000.0,
    "alligator_crack": 25_000.0,
    "d40": 15_000.0,                # pothole
    "pothole": 15_000.0,
}

_DEFAULT_BASE_COST = 12_000.0  # unknown / unrecognized damage type

_SEVERITY_MULTIPLIER = {
    "high": 1.5,
    "medium": 1.0,
    "low": 0.6,
    "unknown": 1.0,
}

# Reuse the SAME road-importance table the priority engine already
# uses, so the cost model and the priority model agree on what counts
# as a "bigger" road. This is a reference, not a rewrite, of the
# priority engine.
_ROAD_IMPORTANCE = PriorityEngine.ROAD_IMPORTANCE
_DEFAULT_ROAD_IMPORTANCE = 35  # matches PriorityEngine's fallback


def estimate_repair_cost(
    damage_type: str | None,
    severity: str | None,
    road_type: str | None,
) -> float:
    """
    ESTIMATE ONLY — not a verified repair cost.

    Used strictly as a fallback for complaints that do not yet have a
    ``Repair.repair_cost`` on record (i.e. not yet repaired), so the
    optimizer has *some* cost to weigh against impact. Deterministic:
    same (damage_type, severity, road_type) always yields the same
    number.

    cost = base_cost(damage_type) * severity_multiplier * road_multiplier,
    rounded to the nearest INR 100 for readability.
    """

    key = (damage_type or "").strip().lower()
    base_cost = _BASE_COST_BY_DAMAGE_TYPE.get(key, _DEFAULT_BASE_COST)

    severity_key = (severity or "unknown").strip().lower()
    severity_mult = _SEVERITY_MULTIPLIER.get(severity_key, 1.0)

    road_key = road_type
    if isinstance(road_key, list):
        road_key = road_key[0] if road_key else None

    road_importance = _ROAD_IMPORTANCE.get(
        str(road_key), _DEFAULT_ROAD_IMPORTANCE
    )
    # Busier/higher-class roads cost more to work on safely (traffic
    # control, night work, etc.) — scaled to a modest 0.8x-1.4x band.
    road_mult = 0.8 + (road_importance / 100.0) * 0.6

    cost = base_cost * severity_mult * road_mult

    return float(round(cost / 100.0) * 100.0)


# --------------------------------------------------------------------
# 3. The real 0/1 knapsack solver
# --------------------------------------------------------------------

# Hard cap on (number_of_candidates * number_of_budget_states) so the
# DP table always stays bounded in memory/time, no matter how many
# eligible complaints or how large the budget is. When the exact
# budget (in whole rupees) already fits under this cap, the DP is
# exact. Otherwise costs are quantized to a coarser rupee "unit" —
# still a real 0/1 knapsack, just over rounded costs — and this is
# reported explicitly in `optimization_method`/`cost_quantization_unit`.
_MAX_DP_CELLS = 2_000_000
_MAX_BUDGET_STATES = 200_000


def _budget_states_and_unit(budget_rupees: int, n_candidates: int) -> tuple[int, int]:
    if n_candidates <= 0:
        return 0, 1

    # How many distinct budget "buckets" we can afford given n items.
    affordable_states = max(1, _MAX_DP_CELLS // n_candidates)
    affordable_states = min(affordable_states, _MAX_BUDGET_STATES)

    if budget_rupees <= affordable_states:
        return budget_rupees, 1

    unit = math.ceil(budget_rupees / affordable_states)
    states = budget_rupees // unit
    return states, unit


def knapsack_01(
    candidates: list[RepairCandidate],
    budget: float,
) -> dict:
    """
    Solve the 0/1 knapsack exactly (subject to the quantization noted
    above) via dynamic programming — i.e. by evaluating combinations
    of candidates, not by sorting on impact or impact/cost ratio.

    Returns a dict with the selected candidates plus solve metadata.
    Never raises on empty input or zero/negative budget: it returns a
    valid empty selection instead.
    """

    budget_rupees = int(round(max(0.0, budget)))

    if not candidates or budget_rupees <= 0:
        return {
            "selected": [],
            "unselected": list(candidates),
            "total_cost": 0.0,
            "total_impact": 0.0,
            "optimization_method": (
                "0/1 knapsack (dynamic programming) — no eligible "
                "candidates or non-positive budget, nothing to select"
            ),
            "cost_quantization_unit": 1,
        }

    n = len(candidates)
    states, unit = _budget_states_and_unit(budget_rupees, n)

    # Cost of each candidate, quantized into `unit`-sized buckets.
    scaled_costs = [
        min(states, max(0, round(c.estimated_cost / unit)))
        for c in candidates
    ]

    # --- Standard 0/1 knapsack DP with rolling value rows -----------
    # prev_dp[w] = best total impact achievable using candidates
    # processed so far, with total scaled cost <= w.
    prev_dp = [0.0] * (states + 1)

    # keep_table[i][w] = 1 iff candidate i is part of the optimal
    # solution for capacity w, given candidates 0..i already
    # considered. One byte per (candidate, budget-state) cell — this
    # is exactly the quantity `_MAX_DP_CELLS` bounds above.
    keep_table = [bytearray(states + 1) for _ in range(n)]

    for i in range(n):
        cost_i = scaled_costs[i]
        impact_i = candidates[i].impact_score
        cur_dp = prev_dp[:]
        keep_row = keep_table[i]

        if cost_i <= states:
            for w in range(cost_i, states + 1):
                candidate_value = prev_dp[w - cost_i] + impact_i
                if candidate_value > cur_dp[w]:
                    cur_dp[w] = candidate_value
                    keep_row[w] = 1

        prev_dp = cur_dp

    # --- Reconstruct which candidates were actually selected ---------
    selected_idx: list[int] = []
    w = states
    for i in range(n - 1, -1, -1):
        if keep_table[i][w]:
            selected_idx.append(i)
            w -= scaled_costs[i]

    selected_idx.reverse()
    selected_ids = set(selected_idx)

    selected = [candidates[i] for i in selected_idx]
    unselected = [
        candidates[i] for i in range(n) if i not in selected_ids
    ]

    total_cost = round(sum(c.estimated_cost for c in selected), 2)
    total_impact = round(sum(c.impact_score for c in selected), 2)

    method = "0/1 knapsack (dynamic programming, evaluates combinations)"
    if unit > 1:
        method += (
            f" — costs quantized to units of INR {unit} to keep the "
            f"DP table tractable; totals below use each candidate's "
            f"real (unquantized) estimated cost"
        )

    return {
        "selected": selected,
        "unselected": unselected,
        "total_cost": total_cost,
        "total_impact": total_impact,
        "optimization_method": method,
        "cost_quantization_unit": unit,
    }
