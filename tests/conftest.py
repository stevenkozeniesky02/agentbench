"""Shared fixtures for AgentBench test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Make tests/ importable so test modules can do `from helpers import ...`
sys.path.insert(0, str(Path(__file__).resolve().parent))

from helpers import (  # noqa: E402
    MockAdapter,
    make_benchmark_run,
    make_challenge,
    make_challenge_result,
    make_score_breakdown,
)
from agentbench.models import (  # noqa: E402
    BenchmarkRun,
    Challenge,
    ChallengeResult,
    ScoreBreakdown,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_challenge() -> Challenge:
    return make_challenge()


@pytest.fixture()
def sample_score_breakdown() -> ScoreBreakdown:
    return make_score_breakdown()


@pytest.fixture()
def sample_challenge_result() -> ChallengeResult:
    return make_challenge_result()


@pytest.fixture()
def sample_benchmark_run() -> BenchmarkRun:
    return make_benchmark_run()


@pytest.fixture()
def mock_adapter() -> MockAdapter:
    return MockAdapter(files_to_create=["main.py"])


@pytest.fixture()
def tmp_challenges(tmp_path: Path) -> Path:
    """Create a temporary challenges directory with tier subdirs and YAML files."""
    easy_dir = tmp_path / "challenges" / "easy"
    easy_dir.mkdir(parents=True)
    medium_dir = tmp_path / "challenges" / "medium"
    medium_dir.mkdir(parents=True)

    easy_challenge = {
        "name": "Password Generator",
        "tier": "easy",
        "language": "python",
        "prompt": "Build a password generator CLI.",
        "expected_files": ["main.py", "tests/test_main.py"],
        "test_commands": ["pytest"],
        "scoring_rubric": {"correctness": 60, "style": 40},
        "time_limit_minutes": 20,
        "setup_commands": ["pip install -e ."],
    }
    (easy_dir / "password-gen.yaml").write_text(
        yaml.dump(easy_challenge, default_flow_style=False), encoding="utf-8"
    )

    easy_challenge_2 = {
        "name": "URL Shortener",
        "tier": "easy",
        "language": "python",
        "prompt": "Build a URL shortener.",
        "expected_files": ["app.py"],
        "test_commands": ["pytest"],
        "scoring_rubric": {"correctness": 70, "style": 30},
    }
    (easy_dir / "url-shortener.yml").write_text(
        yaml.dump(easy_challenge_2, default_flow_style=False), encoding="utf-8"
    )

    medium_challenge = {
        "name": "REST API",
        "tier": "medium",
        "language": "python",
        "prompt": "Build a REST API with Flask.",
        "expected_files": ["app.py", "tests/"],
        "test_commands": ["pytest"],
        "scoring_rubric": {"correctness": 50, "design": 50},
        "time_limit_minutes": 45,
    }
    (medium_dir / "rest-api.yaml").write_text(
        yaml.dump(medium_challenge, default_flow_style=False), encoding="utf-8"
    )

    return tmp_path / "challenges"
