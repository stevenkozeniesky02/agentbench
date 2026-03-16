"""Tests for agentbench.cli -- Click CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from agentbench.cli import main
from agentbench.report import save_results
from helpers import make_benchmark_run, make_challenge, make_challenge_result


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


class TestListCommand:

    @patch("agentbench.cli.load_all")
    def test_list_shows_challenges(self, mock_load_all, runner: CliRunner) -> None:
        mock_load_all.return_value = [
            make_challenge(id="easy/a", name="Alpha"),
            make_challenge(id="medium/b", name="Bravo", tier="medium"),
        ]
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "Alpha" in result.output
        assert "Bravo" in result.output

    @patch("agentbench.cli.load_all")
    def test_list_no_challenges(self, mock_load_all, runner: CliRunner) -> None:
        mock_load_all.return_value = []
        result = runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "No challenges found" in result.output

    @patch("agentbench.cli.load_all")
    def test_list_handles_file_not_found(self, mock_load_all, runner: CliRunner) -> None:
        mock_load_all.side_effect = FileNotFoundError("not found")
        result = runner.invoke(main, ["list"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# run command -- validation
# ---------------------------------------------------------------------------


class TestRunCommandValidation:

    def test_no_selection_raises_error(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["run", "--agent", "test"])
        assert result.exit_code != 0
        assert "exactly one" in result.output.lower() or result.exit_code == 1

    def test_multiple_selections_raises_error(self, runner: CliRunner) -> None:
        result = runner.invoke(
            main, ["run", "--agent", "test", "--tier", "easy", "--all"]
        )
        assert result.exit_code != 0

    @patch("agentbench.cli.find_challenge")
    def test_unknown_agent_raises_error(
        self, mock_find, runner: CliRunner
    ) -> None:
        mock_find.return_value = make_challenge()
        result = runner.invoke(
            main, ["run", "--agent", "nonexistent", "--challenge", "easy/a"]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# compare command
# ---------------------------------------------------------------------------


class TestCompareCommand:

    def test_compare_with_two_files(self, runner: CliRunner, tmp_path: Path) -> None:
        r1 = make_challenge_result(challenge_id="easy/a", agent_name="a1", total_score=70.0)
        r2 = make_challenge_result(challenge_id="easy/a", agent_name="a2", total_score=50.0)
        run1 = make_benchmark_run(agent_name="a1", results=[r1], aggregate_score=70.0)
        run2 = make_benchmark_run(agent_name="a2", results=[r2], aggregate_score=50.0)

        f1 = tmp_path / "a1.json"
        f2 = tmp_path / "a2.json"
        save_results(run1, f1)
        save_results(run2, f2)

        result = runner.invoke(main, ["compare", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "a1" in result.output
        assert "a2" in result.output

    def test_compare_single_file_errors(self, runner: CliRunner, tmp_path: Path) -> None:
        f1 = tmp_path / "only.json"
        save_results(make_benchmark_run(), f1)
        result = runner.invoke(main, ["compare", str(f1)])
        assert result.exit_code != 0

    def test_compare_no_files_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["compare"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# report command
# ---------------------------------------------------------------------------


class TestReportCommand:

    def test_report_prints_markdown(self, runner: CliRunner, tmp_path: Path) -> None:
        r1 = make_challenge_result(challenge_id="easy/a", agent_name="a1", total_score=70.0)
        r2 = make_challenge_result(challenge_id="easy/a", agent_name="a2", total_score=50.0)
        run1 = make_benchmark_run(agent_name="a1", results=[r1], aggregate_score=70.0)
        run2 = make_benchmark_run(agent_name="a2", results=[r2], aggregate_score=50.0)

        results_dir = tmp_path / "results"
        results_dir.mkdir()
        save_results(run1, results_dir / "a1.json")
        save_results(run2, results_dir / "a2.json")

        result = runner.invoke(main, ["report", str(results_dir)])
        assert result.exit_code == 0
        assert "AgentBench" in result.output

    def test_report_saves_to_file(self, runner: CliRunner, tmp_path: Path) -> None:
        r1 = make_challenge_result(challenge_id="easy/x", agent_name="a1", total_score=60.0)
        r2 = make_challenge_result(challenge_id="easy/x", agent_name="a2", total_score=40.0)
        run1 = make_benchmark_run(agent_name="a1", results=[r1], aggregate_score=60.0)
        run2 = make_benchmark_run(agent_name="a2", results=[r2], aggregate_score=40.0)

        results_dir = tmp_path / "results"
        results_dir.mkdir()
        save_results(run1, results_dir / "a1.json")
        save_results(run2, results_dir / "a2.json")

        output_file = tmp_path / "report.md"
        result = runner.invoke(
            main, ["report", str(results_dir), "--output", str(output_file)]
        )
        assert result.exit_code == 0
        assert output_file.is_file()
        content = output_file.read_text(encoding="utf-8")
        assert "AgentBench" in content

    def test_report_nonexistent_dir_errors(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["report", str(tmp_path / "nope")])
        assert result.exit_code != 0

    def test_report_empty_dir_errors(self, runner: CliRunner, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(main, ["report", str(empty)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


class TestVersion:

    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "agentbench" in result.output.lower()
