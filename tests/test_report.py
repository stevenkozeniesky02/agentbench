"""Tests for agentbench.report -- JSON serialization, comparison, and full reports."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentbench.models import BenchmarkRun
from agentbench.report import (
    compare_runs,
    generate_full_report,
    generate_result_json,
    load_results,
    save_results,
)
from helpers import make_benchmark_run, make_challenge_result


# ---------------------------------------------------------------------------
# generate_result_json
# ---------------------------------------------------------------------------


class TestGenerateResultJson:

    def test_produces_valid_json(self) -> None:
        run = make_benchmark_run()
        text = generate_result_json(run)
        data = json.loads(text)
        assert data["agent_name"] == "test-agent"
        assert isinstance(data["results"], list)

    def test_json_is_pretty_printed(self) -> None:
        run = make_benchmark_run()
        text = generate_result_json(run)
        assert "\n" in text
        # 2-space indent means lines should start with "  "
        lines = text.splitlines()
        indented = [l for l in lines if l.startswith("  ")]
        assert len(indented) > 0


# ---------------------------------------------------------------------------
# save_results / load_results roundtrip
# ---------------------------------------------------------------------------


class TestSaveAndLoadResults:

    def test_roundtrip(self, tmp_path: Path) -> None:
        original = make_benchmark_run()
        out_path = tmp_path / "results.json"
        saved = save_results(original, out_path)

        assert saved.is_file()

        loaded = load_results(out_path)
        assert isinstance(loaded, BenchmarkRun)
        assert loaded.agent_name == original.agent_name
        assert loaded.aggregate_score == original.aggregate_score
        assert len(loaded.results) == len(original.results)
        assert loaded.results[0].challenge_id == original.results[0].challenge_id

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "c" / "results.json"
        save_results(make_benchmark_run(), deep_path)
        assert deep_path.is_file()

    def test_load_nonexistent_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_results(tmp_path / "nope.json")

    def test_load_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid json", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_results(bad)

    def test_load_non_object_json_raises_value_error(self, tmp_path: Path) -> None:
        arr = tmp_path / "arr.json"
        arr.write_text("[1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a JSON object"):
            load_results(arr)

    def test_load_missing_keys_raises_value_error(self, tmp_path: Path) -> None:
        partial = tmp_path / "partial.json"
        partial.write_text(json.dumps({"agent_name": "x"}), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required keys"):
            load_results(partial)


# ---------------------------------------------------------------------------
# compare_runs
# ---------------------------------------------------------------------------


class TestCompareRuns:

    def _make_two_runs(self) -> list[BenchmarkRun]:
        r1 = make_challenge_result(
            challenge_id="easy/a", agent_name="agent-1", total_score=80.0
        )
        r2 = make_challenge_result(
            challenge_id="easy/a", agent_name="agent-2", total_score=60.0
        )
        run1 = make_benchmark_run(agent_name="agent-1", results=[r1], aggregate_score=80.0)
        run2 = make_benchmark_run(agent_name="agent-2", results=[r2], aggregate_score=60.0)
        return [run1, run2]

    def test_requires_at_least_two_runs(self) -> None:
        with pytest.raises(ValueError, match="(?i)at least two"):
            compare_runs([make_benchmark_run()])

    def test_contains_header(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "# AgentBench Comparison Report" in md

    def test_contains_summary_section(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "## Summary" in md
        assert "agent-1" in md
        assert "agent-2" in md

    def test_contains_per_tier_breakdown(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "## Per-Tier Breakdown" in md
        assert "easy" in md

    def test_contains_per_challenge_results(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "## Per-Challenge Results" in md
        assert "easy/a" in md

    def test_contains_methodology_section(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "## Methodology" in md
        assert "Build Success" in md

    def test_bold_winner(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "**80.0**" in md

    def test_generated_footer(self) -> None:
        runs = self._make_two_runs()
        md = compare_runs(runs)
        assert "*Generated by AgentBench*" in md


# ---------------------------------------------------------------------------
# generate_full_report
# ---------------------------------------------------------------------------


class TestGenerateFullReport:

    def _write_run(self, directory: Path, run: BenchmarkRun, filename: str) -> None:
        save_results(run, directory / filename)

    def test_generates_markdown(self, tmp_path: Path) -> None:
        r1 = make_challenge_result(challenge_id="easy/a", agent_name="a1", total_score=70.0)
        r2 = make_challenge_result(challenge_id="easy/a", agent_name="a2", total_score=50.0)
        run1 = make_benchmark_run(agent_name="a1", results=[r1], aggregate_score=70.0)
        run2 = make_benchmark_run(agent_name="a2", results=[r2], aggregate_score=50.0)

        results_dir = tmp_path / "results"
        results_dir.mkdir()
        self._write_run(results_dir, run1, "a1.json")
        self._write_run(results_dir, run2, "a2.json")

        md = generate_full_report(results_dir)
        assert "# AgentBench Comparison Report" in md
        assert "a1" in md
        assert "a2" in md

    def test_nonexistent_dir_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            generate_full_report(tmp_path / "nope")

    def test_empty_dir_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(ValueError, match="No .json files"):
            generate_full_report(empty)

    def test_single_file_raises(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        run = make_benchmark_run()
        self._write_run(results_dir, run, "only.json")
        with pytest.raises(ValueError, match="at least 2"):
            generate_full_report(results_dir)
