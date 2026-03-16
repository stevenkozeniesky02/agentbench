"""Tests for agentbench.runner -- challenge execution and aggregation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agentbench.models import BenchmarkRun, ChallengeResult
from agentbench.runner import (
    _compute_aggregate,
    _measure_completeness,
    run_benchmark,
    run_challenge,
    run_tier,
)
from helpers import MockAdapter, make_challenge, make_challenge_result


# ---------------------------------------------------------------------------
# _measure_completeness
# ---------------------------------------------------------------------------


class TestMeasureCompleteness:

    def test_all_files_present(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass\n")
        (tmp_path / "b.py").write_text("pass\n")
        assert _measure_completeness(tmp_path, ["a.py", "b.py"]) == pytest.approx(1.0)

    def test_some_files_missing(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("pass\n")
        assert _measure_completeness(tmp_path, ["a.py", "b.py"]) == pytest.approx(0.5)

    def test_no_files_present(self, tmp_path: Path) -> None:
        assert _measure_completeness(tmp_path, ["a.py"]) == pytest.approx(0.0)

    def test_empty_expected_returns_1(self, tmp_path: Path) -> None:
        assert _measure_completeness(tmp_path, []) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _compute_aggregate
# ---------------------------------------------------------------------------


class TestComputeAggregate:

    def test_empty_results(self) -> None:
        assert _compute_aggregate([]) == 0.0

    def test_single_result(self) -> None:
        r = make_challenge_result(total_score=72.0)
        assert _compute_aggregate([r]) == pytest.approx(72.0)

    def test_multiple_results(self) -> None:
        r1 = make_challenge_result(total_score=60.0)
        r2 = make_challenge_result(total_score=80.0)
        assert _compute_aggregate([r1, r2]) == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# run_challenge
# ---------------------------------------------------------------------------


class TestRunChallenge:

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_run_challenge_produces_result(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = (True, [])
        mock_tests.return_value = (True, 5, 5, [])
        mock_coverage.return_value = 85.0
        mock_quality.return_value = {
            "file_count": 2,
            "avg_file_size": 50.0,
            "avg_complexity": 3.0,
        }

        adapter = MockAdapter(files_to_create=["main.py"])
        challenge = make_challenge(expected_files=["main.py"])

        result = run_challenge(adapter, challenge, tmp_path)

        assert isinstance(result, ChallengeResult)
        assert result.challenge_id == "easy/sample"
        assert result.agent_name == "mock-agent"
        assert result.score_breakdown.does_it_build is True
        assert result.score_breakdown.tests_passed_count == 5
        assert result.total_score > 0
        assert result.errors == []

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_run_challenge_collects_adapter_error(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = (False, ["build broke"])
        mock_tests.return_value = (False, 0, 5, ["tests broke"])
        mock_coverage.return_value = 0.0
        mock_quality.return_value = {
            "file_count": 0,
            "avg_file_size": 0.0,
            "avg_complexity": 10.0,
        }

        adapter = MockAdapter(success=False, error="adapter failed")
        challenge = make_challenge()

        result = run_challenge(adapter, challenge, tmp_path)

        assert "adapter failed" in result.errors
        assert "build broke" in result.errors
        assert "tests broke" in result.errors

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_coverage_clamped_to_one(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = (True, [])
        mock_tests.return_value = (True, 1, 1, [])
        mock_coverage.return_value = 150.0  # unrealistic but tests clamping
        mock_quality.return_value = {"file_count": 1, "avg_file_size": 10, "avg_complexity": 2}

        adapter = MockAdapter()
        challenge = make_challenge()
        result = run_challenge(adapter, challenge, tmp_path)

        assert result.score_breakdown.test_coverage <= 1.0


# ---------------------------------------------------------------------------
# run_tier
# ---------------------------------------------------------------------------


class TestRunTier:

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_runs_all_challenges(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = (True, [])
        mock_tests.return_value = (True, 3, 3, [])
        mock_coverage.return_value = 80.0
        mock_quality.return_value = {"file_count": 1, "avg_file_size": 50, "avg_complexity": 4}

        adapter = MockAdapter()
        challenges = [
            make_challenge(id="easy/a", name="A"),
            make_challenge(id="easy/b", name="B"),
        ]

        results = run_tier(adapter, challenges, tmp_path)
        assert len(results) == 2
        assert results[0].challenge_id == "easy/a"
        assert results[1].challenge_id == "easy/b"


# ---------------------------------------------------------------------------
# run_benchmark
# ---------------------------------------------------------------------------


class TestRunBenchmark:

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_produces_benchmark_run(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = (True, [])
        mock_tests.return_value = (True, 5, 5, [])
        mock_coverage.return_value = 90.0
        mock_quality.return_value = {"file_count": 2, "avg_file_size": 80, "avg_complexity": 3}

        adapter = MockAdapter()
        challenges = [make_challenge(id="easy/x")]

        run = run_benchmark(adapter, challenges, tmp_path, metadata={"env": "test"})

        assert isinstance(run, BenchmarkRun)
        assert run.agent_name == "mock-agent"
        assert len(run.results) == 1
        assert run.aggregate_score > 0
        assert run.metadata == {"env": "test"}

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_empty_challenges_gives_zero_aggregate(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        adapter = MockAdapter()
        run = run_benchmark(adapter, [], tmp_path)
        assert run.aggregate_score == 0.0
        assert run.results == []

    @patch("agentbench.runner.measure_quality")
    @patch("agentbench.runner.measure_coverage")
    @patch("agentbench.runner.run_tests")
    @patch("agentbench.runner.check_build")
    def test_default_metadata_is_empty_dict(
        self,
        mock_build,
        mock_tests,
        mock_coverage,
        mock_quality,
        tmp_path: Path,
    ) -> None:
        mock_build.return_value = (True, [])
        mock_tests.return_value = (True, 1, 1, [])
        mock_coverage.return_value = 50.0
        mock_quality.return_value = {"file_count": 1, "avg_file_size": 10, "avg_complexity": 5}

        adapter = MockAdapter()
        run = run_benchmark(adapter, [make_challenge()], tmp_path)
        assert run.metadata == {}
