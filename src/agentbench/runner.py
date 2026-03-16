"""Benchmark runner -- orchestrates challenges, metrics, and scoring."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agentbench.adapters.base import AgentAdapter
from agentbench.metrics import check_build, measure_coverage, measure_quality, run_tests
from agentbench.models import (
    BenchmarkRun,
    Challenge,
    ChallengeResult,
    ScoreBreakdown,
    compute_total_score,
)

logger = logging.getLogger(__name__)


def _measure_completeness(output_dir: Path, expected_files: list[str]) -> float:
    """Return the fraction of expected files that exist in output_dir (0.0--1.0)."""
    if not expected_files:
        return 1.0
    found = sum(1 for f in expected_files if (output_dir / f).exists())
    return found / len(expected_files)


def run_challenge(
    adapter: AgentAdapter,
    challenge: Challenge,
    base_output_dir: Path,
) -> ChallengeResult:
    """Run a single challenge through the adapter and collect all metrics.

    Args:
        adapter: The agent adapter to execute the challenge.
        challenge: Challenge definition with prompt, expected files, etc.
        base_output_dir: Parent directory; output goes into a subdirectory
            named after the challenge id.

    Returns:
        A fully-scored ChallengeResult.
    """
    output_dir = base_output_dir / challenge.id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Running challenge %s with adapter %s", challenge.id, adapter.name)

    adapter_result = adapter.run_challenge(
        prompt=challenge.prompt,
        output_dir=output_dir,
        time_limit_minutes=challenge.time_limit_minutes,
    )

    errors: list[str] = []
    if adapter_result.error is not None:
        errors.append(adapter_result.error)

    # -- Completeness --
    completeness = _measure_completeness(output_dir, challenge.expected_files)

    # -- Build --
    build_ok, build_errors = check_build(output_dir, challenge.setup_commands)
    errors = [*errors, *build_errors]

    # -- Tests --
    tests_pass, passed_count, total_count, test_errors = run_tests(
        output_dir, challenge.test_commands
    )
    errors = [*errors, *test_errors]

    # -- Coverage --
    coverage_pct = measure_coverage(output_dir, challenge.language)
    coverage_fraction = min(coverage_pct / 100.0, 1.0)

    # -- Code quality --
    code_quality = measure_quality(output_dir, challenge.language)

    breakdown = ScoreBreakdown(
        does_it_build=build_ok,
        tests_pass=tests_pass,
        tests_passed_count=passed_count,
        tests_total_count=total_count,
        test_coverage=coverage_fraction,
        code_quality=code_quality,
        completeness=completeness,
        time_taken_seconds=adapter_result.time_taken_seconds,
        prompts_used=adapter_result.prompts_used,
    )

    total_score = compute_total_score(breakdown)

    timestamp = datetime.now(timezone.utc).isoformat()

    return ChallengeResult(
        challenge_id=challenge.id,
        agent_name=adapter.name,
        score_breakdown=breakdown,
        total_score=total_score,
        output_dir=str(output_dir),
        timestamp=timestamp,
        errors=errors,
    )


def run_tier(
    adapter: AgentAdapter,
    challenges: list[Challenge],
    base_output_dir: Path,
) -> list[ChallengeResult]:
    """Run a list of challenges sequentially, returning all results.

    Args:
        adapter: The agent adapter to use for every challenge.
        challenges: Ordered list of challenges to execute.
        base_output_dir: Parent directory for all challenge output.

    Returns:
        A list of ChallengeResult, one per challenge.
    """
    return [
        run_challenge(adapter, challenge, base_output_dir)
        for challenge in challenges
    ]


def run_benchmark(
    adapter: AgentAdapter,
    challenges: list[Challenge],
    base_output_dir: Path,
    metadata: dict[str, Any] | None = None,
) -> BenchmarkRun:
    """Run a full benchmark suite and compute aggregate scores.

    Args:
        adapter: The agent adapter to use.
        challenges: All challenges to run.
        base_output_dir: Parent directory for all challenge output.
        metadata: Optional extra metadata to attach to the run.

    Returns:
        A BenchmarkRun containing individual results and the aggregate score.
    """
    results = run_tier(adapter, challenges, base_output_dir)

    aggregate_score = _compute_aggregate(results)
    timestamp = datetime.now(timezone.utc).isoformat()

    return BenchmarkRun(
        agent_name=adapter.name,
        results=results,
        aggregate_score=aggregate_score,
        timestamp=timestamp,
        metadata=metadata or {},
    )


def _compute_aggregate(results: list[ChallengeResult]) -> float:
    """Compute the mean total_score across all results.

    Returns 0.0 when the results list is empty.
    """
    if not results:
        return 0.0
    return sum(r.total_score for r in results) / len(results)
