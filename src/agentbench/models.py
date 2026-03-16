"""Immutable data models for AgentBench benchmark results and challenges."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Challenge:
    """Represents a benchmark challenge loaded from YAML."""

    id: str
    name: str
    tier: str
    language: str
    prompt: str
    expected_files: list[str]
    test_commands: list[str]
    scoring_rubric: dict[str, Any]
    time_limit_minutes: int = 30
    setup_commands: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreBreakdown:
    """Individual scoring components for a challenge result."""

    does_it_build: bool
    tests_pass: bool
    tests_passed_count: int
    tests_total_count: int
    test_coverage: float
    code_quality: dict[str, Any]
    completeness: float
    time_taken_seconds: float
    prompts_used: int


@dataclass(frozen=True)
class ChallengeResult:
    """Result of running one challenge for a specific agent."""

    challenge_id: str
    agent_name: str
    score_breakdown: ScoreBreakdown
    total_score: float
    output_dir: str
    timestamp: str
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary suitable for JSON output."""
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class BenchmarkRun:
    """Full benchmark run results across all challenges for an agent."""

    agent_name: str
    results: list[ChallengeResult]
    aggregate_score: float
    timestamp: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dictionary suitable for JSON output."""
        return dataclasses.asdict(self)


def _compute_quality_score(code_quality: dict[str, Any]) -> float:
    """Derive a 0.0-1.0 quality score from average cyclomatic complexity."""
    avg_complexity = code_quality.get("avg_complexity", 0.0)
    if avg_complexity < 5:
        return 1.0
    if avg_complexity < 10:
        return 0.5
    if avg_complexity < 20:
        return 0.2
    return 0.0


def compute_total_score(breakdown: ScoreBreakdown) -> float:
    """Compute a 0-100 total score from a ScoreBreakdown.

    Scoring weights:
        - builds:      25 points if does_it_build is True
        - tests_pass:  20 * (tests_passed_count / max(tests_total_count, 1))
        - coverage:    15 * test_coverage
        - code_quality: 15 * quality_score (based on avg_complexity)
        - completeness: 15 * completeness
        - efficiency:  10 * max(0, 1.0 - time_taken_seconds / 1800)
    """
    builds = 25.0 if breakdown.does_it_build else 0.0

    tests_denominator = max(breakdown.tests_total_count, 1)
    tests = 20.0 * (breakdown.tests_passed_count / tests_denominator)

    coverage = 15.0 * breakdown.test_coverage

    quality = 15.0 * _compute_quality_score(breakdown.code_quality)

    completeness = 15.0 * breakdown.completeness

    efficiency = 10.0 * max(0.0, 1.0 - (breakdown.time_taken_seconds / 1800.0))

    return builds + tests + coverage + quality + completeness + efficiency
