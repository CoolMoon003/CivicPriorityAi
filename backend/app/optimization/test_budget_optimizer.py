"""
Deterministic test for the 0/1 knapsack budget optimizer.

NOT connected to the production database — uses hand-built
RepairCandidate objects only, per Task 9 instructions ("DO NOT insert
these values into production database").

Scenario (from the task spec):

    Budget = INR 100,000
    A: impact=80, cost=70,000
    B: impact=60, cost=30,000
    C: impact=65, cost=40,000

A naive "sort by impact, take greedily" approach would pick A first
(highest single impact = 80) and then be unable to afford B or C
(70,000 + 30,000 = 100,000 fits, but 70,000 + 40,000 = 110,000 does
not) — so greedy-by-impact alone would stop at {A}, impact = 80.

The TRUE optimum, found only by evaluating combinations, is {A, B}:
cost = 70,000 + 30,000 = 100,000 (exactly the budget), impact = 140.
This beats both {A} alone (80) and {B, C} (125), which is exactly
what a real 0/1 knapsack must prove versus a naive single-item pick.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from backend.app.optimization.budget_optimizer import (  # noqa: E402
    RepairCandidate,
    estimate_repair_cost,
    knapsack_01,
)


def _make_candidates():
    return [
        RepairCandidate(
            complaint_id=1,
            impact_score=80,
            estimated_cost=70_000,
            cost_is_estimated=True,
        ),
        RepairCandidate(
            complaint_id=2,
            impact_score=60,
            estimated_cost=30_000,
            cost_is_estimated=True,
        ),
        RepairCandidate(
            complaint_id=3,
            impact_score=65,
            estimated_cost=40_000,
            cost_is_estimated=True,
        ),
    ]


def test_optimizer_beats_naive_single_highest_impact_pick():
    result = knapsack_01(_make_candidates(), budget=100_000)

    selected_ids = sorted(c.complaint_id for c in result["selected"])

    # True optimum is {A, B}, not {A} alone and not {B, C}.
    assert selected_ids == [1, 2], (
        f"expected complaints [1, 2] (A+B) selected, got {selected_ids}"
    )

    assert result["total_cost"] == 100_000
    assert result["total_impact"] == 140

    # Prove it is strictly better than the naive "just take the
    # single highest-impact item" answer (A alone, impact 80) and
    # better than the other plausible pair (B+C, impact 125).
    assert result["total_impact"] > 80
    assert result["total_impact"] > 125


def test_empty_candidates_returns_valid_empty_result():
    result = knapsack_01([], budget=50_000)

    assert result["selected"] == []
    assert result["total_cost"] == 0.0
    assert result["total_impact"] == 0.0


def test_non_positive_budget_returns_valid_empty_result():
    result = knapsack_01(_make_candidates(), budget=0)

    assert result["selected"] == []
    assert result["total_cost"] == 0.0
    assert result["total_impact"] == 0.0


def test_estimate_repair_cost_is_deterministic():
    a = estimate_repair_cost("D40", "high", "primary")
    b = estimate_repair_cost("D40", "high", "primary")

    assert a == b
    assert a > 0


def test_estimate_repair_cost_handles_unknown_damage_type():
    # Must not raise, and must still return a positive deterministic
    # estimate for a damage type not in the known map.
    cost = estimate_repair_cost("some_unrecognized_type", "unknown", None)
    assert cost > 0


if __name__ == "__main__":
    test_optimizer_beats_naive_single_highest_impact_pick()
    test_empty_candidates_returns_valid_empty_result()
    test_non_positive_budget_returns_valid_empty_result()
    test_estimate_repair_cost_is_deterministic()
    test_estimate_repair_cost_handles_unknown_damage_type()
    print("All budget_optimizer tests passed.")
