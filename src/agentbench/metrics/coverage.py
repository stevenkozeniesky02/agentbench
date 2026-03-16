"""Code-coverage metric for AgentBench."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_COVERAGE_TIMEOUT_SECONDS = 300

# Patterns for extracting coverage percentages from various tools.
_PYTEST_COV_TOTAL = re.compile(r"^TOTAL\s+.*?(\d+)%", re.MULTILINE)
_JEST_COVERAGE = re.compile(r"All files\s*\|\s*[\d.]+\s*\|\s*[\d.]+\s*\|\s*[\d.]+\s*\|\s*([\d.]+)")
_GO_COVERAGE = re.compile(r"coverage:\s*([\d.]+)%")

_LANGUAGE_COMMANDS: dict[str, str] = {
    "python": "pytest --cov --cov-report=term -q",
    "typescript": "npx jest --coverage",
    "go": "go test -cover ./...",
}

_LANGUAGE_PARSERS: dict[str, re.Pattern[str]] = {
    "python": _PYTEST_COV_TOTAL,
    "typescript": _JEST_COVERAGE,
    "go": _GO_COVERAGE,
}


def _parse_coverage(output: str, language: str) -> float:
    """Extract a coverage percentage from command output."""
    pattern = _LANGUAGE_PARSERS.get(language)
    if pattern is None:
        return 0.0

    match = pattern.search(output)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, IndexError):
            return 0.0
    return 0.0


def measure_coverage(output_dir: Path, language: str) -> float:
    """Measure code-coverage percentage for a project.

    Args:
        output_dir: Project root directory.
        language: One of ``"python"``, ``"typescript"``, ``"go"``, ``"rust"``.

    Returns:
        Coverage as a percentage (0.0 -- 100.0).  Returns ``0.0`` when
        coverage cannot be determined or the language is unsupported.
    """
    language = language.lower()

    if language == "rust":
        logger.info("Rust coverage measurement is not supported; returning 0.0")
        return 0.0

    command = _LANGUAGE_COMMANDS.get(language)
    if command is None:
        logger.warning("Unsupported language for coverage: %s", language)
        return 0.0

    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=_COVERAGE_TIMEOUT_SECONDS,
        )
        combined_output = f"{result.stdout}\n{result.stderr}"
        coverage = _parse_coverage(combined_output, language)
        return coverage
    except subprocess.TimeoutExpired:
        logger.warning(
            "Coverage command timed out after %ds: %s",
            _COVERAGE_TIMEOUT_SECONDS,
            command,
        )
        return 0.0
    except OSError as exc:
        logger.warning("Failed to execute coverage command: %s (%s)", command, exc)
        return 0.0
