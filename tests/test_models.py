"""Tests for agentbench.models -- immutable dataclasses and scoring logic."""

from __future__ import annotations

import dataclasses

import pytest

from agentbench.models import (
    BenchmarkRun,
    Challenge,
    ChallengeResult,
    ScoreBreakdown,
    _compute_quality_score,
    compute_total_score,
)
from helpers import make_challenge, make_challenge_result, make_score_breakdown


# ---------------------------------------------------------------------------
# Frozen dataclass immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    """Verify that all frozen dataclasses reject mutation."""

    def test_challenge_is_frozen(self, sample_challenge: Challenge) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_challenge.name = "changed"  # type: ignore[misc]

    def test_score_breakdown_is_frozen(self, sample_score_breakdown: ScoreBreakdown) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_score_breakdown.does_it_build = False  # type: ignore[misc]

    def test_challenge_result_is_frozen(self, sample_challenge_result: ChallengeResult) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_challenge_result.total_score = 0.0  # type: ignore[misc]

    def test_benchmark_run_is_frozen(self, sample_benchmark_run: BenchmarkRun) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_benchmark_run.agent_name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ChallengeResult and BenchmarkRun serialization
# ---------------------------------------------------------------------------


class TestSerialization:

    def test_challenge_result_to_dict(self) -> None:
        result = make_challenge_result()
        d = result.to_dict()
        assert d["challenge_id"] == "easy/sample"
        assert d["agent_name"] == "test-agent"
        assert isinstance(d["score_breakdown"], dict)
        assert d["score_breakdown"]["does_it_build"] is True

    def test_benchmark_run_to_dict(self) -> None:
        run = BenchmarkRun(
            agent_name="agent-x",
            results=[make_challenge_result()],
            aggregate_score=85.0,
            timestamp="2026-01-01T00:00:00+00:00",
            metadata={"foo": "bar"},
        )
        d = run.to_dict()
        assert d["agent_name"] == "agent-x"
        assert len(d["results"]) == 1
        assert d["metadata"]["foo"] == "bar"


# ---------------------------------------------------------------------------
# _compute_quality_score
# ---------------------------------------------------------------------------


class TestComputeQualityScore:

    def test_low_complexity_returns_1(self) -> None:
        assert _compute_quality_score({"avg_complexity": 2.0}) == 1.0

    def test_moderate_complexity_returns_half(self) -> None:
        assert _compute_quality_score({"avg_complexity": 7.0}) == 0.5

    def test_high_complexity_returns_low(self) -> None:
        assert _compute_quality_score({"avg_complexity": 15.0}) == 0.2

    def test_very_high_complexity_returns_zero(self) -> None:
        assert _compute_quality_score({"avg_complexity": 25.0}) == 0.0

    def test_missing_complexity_key_treated_as_zero(self) -> None:
        assert _compute_quality_score({}) == 1.0

    def test_boundary_at_5(self) -> None:
        assert _compute_quality_score({"avg_complexity": 5.0}) == 0.5

    def test_boundary_at_10(self) -> None:
        assert _compute_quality_score({"avg_complexity": 10.0}) == 0.2

    def test_boundary_at_20(self) -> None:
        assert _compute_quality_score({"avg_complexity": 20.0}) == 0.0


# ---------------------------------------------------------------------------
# compute_total_score
# ---------------------------------------------------------------------------


class TestComputeTotalScore:

    def test_perfect_score(self) -> None:
        """Everything passes, low complexity, fast completion."""
        breakdown = make_score_breakdown(
            does_it_build=True,
            tests_pass=True,
            tests_passed_count=10,
            tests_total_count=10,
            test_coverage=1.0,
            code_quality={"avg_complexity": 2.0},
            completeness=1.0,
            time_taken_seconds=0.0,
        )
        score = compute_total_score(breakdown)
        # 25 + 20 + 15 + 15 + 15 + 10 = 100
        assert score == pytest.approx(100.0)

    def test_zero_score(self) -> None:
        """Nothing works -- no build, no tests, no coverage, high complexity, slow."""
        breakdown = make_score_breakdown(
            does_it_build=False,
            tests_pass=False,
            tests_passed_count=0,
            tests_total_count=10,
            test_coverage=0.0,
            code_quality={"avg_complexity": 30.0},
            completeness=0.0,
            time_taken_seconds=1800.0,
        )
        score = compute_total_score(breakdown)
        assert score == pytest.approx(0.0)

    def test_partial_tests(self) -> None:
        breakdown = make_score_breakdown(
            does_it_build=True,
            tests_passed_count=3,
            tests_total_count=10,
            test_coverage=0.5,
            code_quality={"avg_complexity": 7.0},
            completeness=0.6,
            time_taken_seconds=900.0,
        )
        score = compute_total_score(breakdown)
        # build=25, tests=20*(3/10)=6, coverage=15*0.5=7.5,
        # quality=15*0.5=7.5, completeness=15*0.6=9, efficiency=10*(1-900/1800)=5
        expected = 25.0 + 6.0 + 7.5 + 7.5 + 9.0 + 5.0
        assert score == pytest.approx(expected)

    def test_zero_tests_total(self) -> None:
        """When tests_total_count is 0, denominator defaults to 1."""
        breakdown = make_score_breakdown(
            tests_passed_count=0,
            tests_total_count=0,
        )
        score = compute_total_score(breakdown)
        # tests component = 20 * (0/1) = 0
        assert score >= 0.0

    def test_very_long_time_clamps_efficiency_to_zero(self) -> None:
        breakdown = make_score_breakdown(time_taken_seconds=5000.0)
        score = compute_total_score(breakdown)
        # efficiency = max(0, 1 - 5000/1800) => 0
        # Re-compute the rest to verify efficiency is 0
        breakdown_fast = make_score_breakdown(time_taken_seconds=0.0)
        score_fast = compute_total_score(breakdown_fast)
        # Difference should be exactly the efficiency component at 0 seconds = 10
        assert score_fast - score == pytest.approx(10.0)

    def test_high_complexity_reduces_quality(self) -> None:
        low_cx = make_score_breakdown(code_quality={"avg_complexity": 2.0})
        high_cx = make_score_breakdown(code_quality={"avg_complexity": 25.0})
        assert compute_total_score(low_cx) > compute_total_score(high_cx)

    def test_build_failure_loses_25_points(self) -> None:
        passing = make_score_breakdown(does_it_build=True)
        failing = make_score_breakdown(does_it_build=False)
        assert compute_total_score(passing) - compute_total_score(failing) == pytest.approx(25.0)
