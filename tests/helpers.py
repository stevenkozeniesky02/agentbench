"""Reusable test factory functions and mock adapter for AgentBench tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentbench.adapters.base import AdapterResult, AgentAdapter
from agentbench.models import (
    BenchmarkRun,
    Challenge,
    ChallengeResult,
    ScoreBreakdown,
)


def make_challenge(**overrides: Any) -> Challenge:
    """Create a Challenge with sensible defaults, overridden by kwargs."""
    defaults: dict[str, Any] = {
        "id": "easy/sample",
        "name": "Sample Challenge",
        "tier": "easy",
        "language": "python",
        "prompt": "Build a hello-world script.",
        "expected_files": ["main.py"],
        "test_commands": ["pytest"],
        "scoring_rubric": {"correctness": 50, "style": 50},
        "time_limit_minutes": 30,
        "setup_commands": [],
    }
    defaults.update(overrides)
    return Challenge(**defaults)


def make_score_breakdown(**overrides: Any) -> ScoreBreakdown:
    """Create a ScoreBreakdown with sensible defaults."""
    defaults: dict[str, Any] = {
        "does_it_build": True,
        "tests_pass": True,
        "tests_passed_count": 5,
        "tests_total_count": 5,
        "test_coverage": 0.85,
        "code_quality": {"file_count": 3, "avg_file_size": 100.0, "avg_complexity": 3.0},
        "completeness": 1.0,
        "time_taken_seconds": 120.0,
        "prompts_used": 1,
    }
    defaults.update(overrides)
    return ScoreBreakdown(**defaults)


def make_challenge_result(**overrides: Any) -> ChallengeResult:
    """Create a ChallengeResult with sensible defaults."""
    defaults: dict[str, Any] = {
        "challenge_id": "easy/sample",
        "agent_name": "test-agent",
        "score_breakdown": make_score_breakdown(),
        "total_score": 85.0,
        "output_dir": "/tmp/output/easy/sample",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "errors": [],
    }
    defaults.update(overrides)
    return ChallengeResult(**defaults)


def make_benchmark_run(**overrides: Any) -> BenchmarkRun:
    """Create a BenchmarkRun with sensible defaults."""
    defaults: dict[str, Any] = {
        "agent_name": "test-agent",
        "results": [make_challenge_result()],
        "aggregate_score": 85.0,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {},
    }
    defaults.update(overrides)
    return BenchmarkRun(**defaults)


class MockAdapter(AgentAdapter):
    """Deterministic adapter that returns a pre-configured AdapterResult."""

    def __init__(
        self,
        *,
        time_taken_seconds: float = 60.0,
        prompts_used: int = 1,
        success: bool = True,
        error: str | None = None,
        files_to_create: list[str] | None = None,
    ) -> None:
        self._time_taken_seconds = time_taken_seconds
        self._prompts_used = prompts_used
        self._success = success
        self._error = error
        self._files_to_create = files_to_create or []

    @property
    def name(self) -> str:
        return "mock-agent"

    def run_challenge(
        self,
        prompt: str,
        output_dir: Path,
        time_limit_minutes: int = 30,
    ) -> AdapterResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename in self._files_to_create:
            (output_dir / filename).write_text(f"# {filename}\n", encoding="utf-8")
        return AdapterResult(
            time_taken_seconds=self._time_taken_seconds,
            prompts_used=self._prompts_used,
            success=self._success,
            error=self._error,
        )
