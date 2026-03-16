"""Test-execution metric for AgentBench."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_TEST_TIMEOUT_SECONDS = 300

# Patterns for extracting pass/fail counts from common test runners.
_PYTEST_PATTERN = re.compile(
    r"(?P<passed>\d+)\s+passed"
    r"(?:.*?(?P<failed>\d+)\s+failed)?",
)
_GENERIC_PASSED_PATTERN = re.compile(r"(\d+)\s+(?:tests?\s+)?passed", re.IGNORECASE)
_GENERIC_FAILED_PATTERN = re.compile(r"(\d+)\s+(?:tests?\s+)?failed", re.IGNORECASE)


def _parse_test_counts(output: str) -> tuple[int, int] | None:
    """Try to extract (passed, failed) from test runner output.

    Returns ``None`` when the output cannot be parsed.
    """
    # Try pytest-style first: "X passed, Y failed"
    match = _PYTEST_PATTERN.search(output)
    if match:
        passed = int(match.group("passed"))
        failed = int(match.group("failed") or 0)
        return (passed, failed)

    # Fall back to generic patterns
    passed_match = _GENERIC_PASSED_PATTERN.search(output)
    failed_match = _GENERIC_FAILED_PATTERN.search(output)
    if passed_match or failed_match:
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        return (passed, failed)

    return None


def run_tests(
    output_dir: Path,
    test_commands: list[str],
) -> tuple[bool, int, int, list[str]]:
    """Execute test commands and aggregate results.

    Args:
        output_dir: Working directory for execution.
        test_commands: Shell commands that run the project's test suite.

    Returns:
        A tuple of ``(all_pass, passed_count, total_count, errors)``.
    """
    if not test_commands:
        return (True, 0, 0, [])

    total_passed = 0
    total_failed = 0
    errors: list[str] = []

    for command in test_commands:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=_TEST_TIMEOUT_SECONDS,
            )
            combined_output = f"{result.stdout}\n{result.stderr}"
            counts = _parse_test_counts(combined_output)

            if counts is not None:
                passed, failed = counts
                total_passed += passed
                total_failed += failed
            elif result.returncode == 0:
                # Command succeeded but we couldn't parse counts --
                # count as 1 passed test suite.
                total_passed += 1
            else:
                # Command failed and no parseable counts.
                total_failed += 1
                detail = result.stderr.strip() or result.stdout.strip()
                msg = f"Test command failed (exit {result.returncode}): {command}"
                if detail:
                    msg = f"{msg}\n{detail}"
                errors.append(msg)
                logger.warning(msg)

        except subprocess.TimeoutExpired:
            msg = f"Test command timed out after {_TEST_TIMEOUT_SECONDS}s: {command}"
            errors.append(msg)
            total_failed += 1
            logger.warning(msg)
        except OSError as exc:
            msg = f"Failed to execute test command: {command} ({exc})"
            errors.append(msg)
            total_failed += 1
            logger.warning(msg)

    total_count = total_passed + total_failed
    all_pass = total_failed == 0 and total_passed > 0
    return (all_pass, total_passed, total_count, errors)
