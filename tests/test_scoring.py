"""Tests for agentbench.metrics -- build, tests, coverage, quality."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentbench.metrics.build import check_build
from agentbench.metrics.coverage import _parse_coverage, measure_coverage
from agentbench.metrics.quality import (
    _average_file_size,
    _count_files,
    measure_quality,
)
from agentbench.metrics.tests import _parse_test_counts, run_tests


# ---------------------------------------------------------------------------
# check_build
# ---------------------------------------------------------------------------


class TestCheckBuild:

    def test_empty_commands_returns_success(self, tmp_path: Path) -> None:
        ok, errors = check_build(tmp_path, [])
        assert ok is True
        assert errors == []

    @patch("agentbench.metrics.build.subprocess.run")
    def test_all_commands_succeed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        ok, errors = check_build(tmp_path, ["make build", "make install"])
        assert ok is True
        assert errors == []
        assert mock_run.call_count == 2

    @patch("agentbench.metrics.build.subprocess.run")
    def test_failing_command_reports_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stderr="compilation error", stdout=""
        )
        ok, errors = check_build(tmp_path, ["make build"])
        assert ok is False
        assert len(errors) == 1
        assert "Command failed" in errors[0]
        assert "compilation error" in errors[0]

    @patch("agentbench.metrics.build.subprocess.run")
    def test_mixed_commands(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """First command succeeds, second fails."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr="", stdout=""),
            MagicMock(returncode=2, stderr="link error", stdout=""),
        ]
        ok, errors = check_build(tmp_path, ["cmd1", "cmd2"])
        assert ok is False
        assert len(errors) == 1

    @patch("agentbench.metrics.build.subprocess.run")
    def test_timeout_reports_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="make", timeout=120)
        ok, errors = check_build(tmp_path, ["make"])
        assert ok is False
        assert "timed out" in errors[0]

    @patch("agentbench.metrics.build.subprocess.run")
    def test_os_error_reports_error(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = OSError("No such file or directory")
        ok, errors = check_build(tmp_path, ["nonexistent"])
        assert ok is False
        assert "Failed to execute" in errors[0]

    @patch("agentbench.metrics.build.subprocess.run")
    def test_failing_command_uses_stdout_when_no_stderr(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stderr="", stdout="stdout error info"
        )
        ok, errors = check_build(tmp_path, ["cmd"])
        assert ok is False
        assert "stdout error info" in errors[0]


# ---------------------------------------------------------------------------
# _parse_test_counts
# ---------------------------------------------------------------------------


class TestParseTestCounts:

    def test_pytest_all_passed(self) -> None:
        output = "===== 10 passed in 1.23s ====="
        result = _parse_test_counts(output)
        assert result == (10, 0)

    def test_pytest_mixed(self) -> None:
        output = "===== 7 passed, 3 failed in 2.5s ====="
        result = _parse_test_counts(output)
        assert result == (7, 3)

    def test_generic_passed(self) -> None:
        output = "Tests: 5 passed"
        result = _parse_test_counts(output)
        assert result == (5, 0)

    def test_generic_failed_only(self) -> None:
        output = "3 tests failed"
        result = _parse_test_counts(output)
        assert result == (0, 3)

    def test_unparseable_returns_none(self) -> None:
        assert _parse_test_counts("no test info here") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_test_counts("") is None


# ---------------------------------------------------------------------------
# run_tests
# ---------------------------------------------------------------------------


class TestRunTests:

    def test_empty_commands_returns_defaults(self, tmp_path: Path) -> None:
        all_pass, passed, total, errors = run_tests(tmp_path, [])
        assert all_pass is True
        assert passed == 0
        assert total == 0
        assert errors == []

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_all_tests_pass_parsed(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="===== 8 passed in 0.5s =====", stderr=""
        )
        all_pass, passed, total, errors = run_tests(tmp_path, ["pytest"])
        assert all_pass is True
        assert passed == 8
        assert total == 8
        assert errors == []

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_some_tests_fail(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="===== 5 passed, 2 failed in 1.0s =====",
            stderr="",
        )
        all_pass, passed, total, errors = run_tests(tmp_path, ["pytest"])
        assert all_pass is False
        assert passed == 5
        assert total == 7

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_unparseable_success_counts_as_one(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="all good", stderr=""
        )
        all_pass, passed, total, errors = run_tests(tmp_path, ["custom-test"])
        assert all_pass is True
        assert passed == 1
        assert total == 1

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_unparseable_failure_counts_as_one_failed(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stdout="boom", stderr="error details"
        )
        all_pass, passed, total, errors = run_tests(tmp_path, ["broken"])
        assert all_pass is False
        assert passed == 0
        assert total == 1
        assert len(errors) == 1

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_timeout_adds_failed_count(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
        all_pass, passed, total, errors = run_tests(tmp_path, ["pytest"])
        assert all_pass is False
        assert total == 1
        assert "timed out" in errors[0]

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_os_error_adds_failed_count(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = OSError("not found")
        all_pass, passed, total, errors = run_tests(tmp_path, ["pytest"])
        assert all_pass is False
        assert total == 1
        assert "Failed to execute" in errors[0]

    @patch("agentbench.metrics.tests.subprocess.run")
    def test_multiple_commands_aggregate(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="3 passed in 0.1s", stderr=""),
            MagicMock(returncode=0, stdout="5 passed in 0.2s", stderr=""),
        ]
        all_pass, passed, total, errors = run_tests(tmp_path, ["cmd1", "cmd2"])
        assert all_pass is True
        assert passed == 8
        assert total == 8


# ---------------------------------------------------------------------------
# _parse_coverage
# ---------------------------------------------------------------------------


class TestParseCoverage:

    def test_python_coverage(self) -> None:
        output = "TOTAL    120    20    83%"
        assert _parse_coverage(output, "python") == pytest.approx(83.0)

    def test_go_coverage(self) -> None:
        output = "ok  mypackage  0.5s  coverage: 72.3% of statements"
        assert _parse_coverage(output, "go") == pytest.approx(72.3)

    def test_typescript_jest_coverage(self) -> None:
        output = "All files |  85.5 |   80.2 |   90.1 |  88.3"
        assert _parse_coverage(output, "typescript") == pytest.approx(88.3)

    def test_unknown_language_returns_zero(self) -> None:
        assert _parse_coverage("anything", "ruby") == 0.0

    def test_no_match_returns_zero(self) -> None:
        assert _parse_coverage("no coverage info here", "python") == 0.0


# ---------------------------------------------------------------------------
# measure_coverage
# ---------------------------------------------------------------------------


class TestMeasureCoverage:

    @patch("agentbench.metrics.coverage.subprocess.run")
    def test_python_coverage(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            stdout="TOTAL    100    15    85%", stderr=""
        )
        cov = measure_coverage(tmp_path, "python")
        assert cov == pytest.approx(85.0)

    def test_rust_returns_zero(self, tmp_path: Path) -> None:
        cov = measure_coverage(tmp_path, "rust")
        assert cov == 0.0

    def test_unsupported_language_returns_zero(self, tmp_path: Path) -> None:
        cov = measure_coverage(tmp_path, "haskell")
        assert cov == 0.0

    @patch("agentbench.metrics.coverage.subprocess.run")
    def test_timeout_returns_zero(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)
        cov = measure_coverage(tmp_path, "python")
        assert cov == 0.0

    @patch("agentbench.metrics.coverage.subprocess.run")
    def test_os_error_returns_zero(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = OSError("boom")
        cov = measure_coverage(tmp_path, "python")
        assert cov == 0.0


# ---------------------------------------------------------------------------
# quality helpers
# ---------------------------------------------------------------------------


class TestCountFiles:

    def test_counts_python_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        (tmp_path / "c.txt").write_text("not python\n")
        files = _count_files(tmp_path, (".py",))
        assert len(files) == 2

    def test_counts_nested_files(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text("pass\n")
        files = _count_files(tmp_path, (".py",))
        assert len(files) == 1

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert _count_files(tmp_path, (".py",)) == []


class TestAverageFileSize:

    def test_average_lines(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
        (tmp_path / "b.py").write_text("single\n")
        files = list(tmp_path.glob("*.py"))
        avg = _average_file_size(files)
        # a.py = 3 lines, b.py = 1 line => avg = 2.0
        assert avg == pytest.approx(2.0)

    def test_empty_list(self) -> None:
        assert _average_file_size([]) == 0.0


# ---------------------------------------------------------------------------
# measure_quality
# ---------------------------------------------------------------------------


class TestMeasureQuality:

    @patch("agentbench.metrics.quality.subprocess.run")
    def test_python_quality(self, mock_run: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("def main():\n    pass\n")
        mock_run.return_value = MagicMock(
            stdout="Average complexity: A (2.5)", stderr=""
        )
        quality = measure_quality(tmp_path, "python")
        assert quality["file_count"] == 1
        assert quality["avg_complexity"] == pytest.approx(2.5)

    def test_unsupported_language(self, tmp_path: Path) -> None:
        quality = measure_quality(tmp_path, "cobol")
        assert quality["file_count"] == 0
        assert quality["avg_complexity"] == 0.0

    @patch("agentbench.metrics.quality.subprocess.run")
    def test_non_python_uses_default_complexity(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        (tmp_path / "main.go").write_text("package main\n")
        quality = measure_quality(tmp_path, "go")
        assert quality["avg_complexity"] == pytest.approx(5.0)
        # radon should NOT be called for Go
        mock_run.assert_not_called()

    @patch("agentbench.metrics.quality.subprocess.run")
    def test_radon_timeout_uses_default(self, mock_run: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n")
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="radon", timeout=120)
        quality = measure_quality(tmp_path, "python")
        assert quality["avg_complexity"] == pytest.approx(5.0)

    @patch("agentbench.metrics.quality.subprocess.run")
    def test_radon_os_error_uses_default(self, mock_run: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n")
        mock_run.side_effect = OSError("radon not found")
        quality = measure_quality(tmp_path, "python")
        assert quality["avg_complexity"] == pytest.approx(5.0)
