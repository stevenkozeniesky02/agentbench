"""Report generation module for AgentBench benchmark results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentbench.models import (
    BenchmarkRun,
    ChallengeResult,
    ScoreBreakdown,
)


def generate_result_json(run: BenchmarkRun) -> str:
    """Serialize a BenchmarkRun to pretty-printed JSON.

    Args:
        run: The benchmark run to serialize.

    Returns:
        A JSON string with 2-space indentation.
    """
    return json.dumps(run.to_dict(), indent=2, sort_keys=False)


def save_results(run: BenchmarkRun, output_path: Path) -> Path:
    """Save benchmark results as JSON to the given path.

    Creates parent directories if they do not exist.

    Args:
        run: The benchmark run to save.
        output_path: Destination file path.

    Returns:
        The resolved output path.
    """
    resolved = output_path.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(generate_result_json(run), encoding="utf-8")
    return resolved


def _reconstruct_score_breakdown(data: dict[str, Any]) -> ScoreBreakdown:
    """Build an immutable ScoreBreakdown from a plain dictionary."""
    return ScoreBreakdown(
        does_it_build=data["does_it_build"],
        tests_pass=data["tests_pass"],
        tests_passed_count=data["tests_passed_count"],
        tests_total_count=data["tests_total_count"],
        test_coverage=data["test_coverage"],
        code_quality=dict(data["code_quality"]),
        completeness=data["completeness"],
        time_taken_seconds=data["time_taken_seconds"],
        prompts_used=data["prompts_used"],
    )


def _reconstruct_challenge_result(data: dict[str, Any]) -> ChallengeResult:
    """Build an immutable ChallengeResult from a plain dictionary."""
    return ChallengeResult(
        challenge_id=data["challenge_id"],
        agent_name=data["agent_name"],
        score_breakdown=_reconstruct_score_breakdown(data["score_breakdown"]),
        total_score=data["total_score"],
        output_dir=data["output_dir"],
        timestamp=data["timestamp"],
        errors=list(data.get("errors", [])),
    )


def _reconstruct_benchmark_run(data: dict[str, Any]) -> BenchmarkRun:
    """Build an immutable BenchmarkRun from a plain dictionary."""
    results = [_reconstruct_challenge_result(r) for r in data["results"]]
    return BenchmarkRun(
        agent_name=data["agent_name"],
        results=results,
        aggregate_score=data["aggregate_score"],
        timestamp=data["timestamp"],
        metadata=dict(data.get("metadata", {})),
    )


def load_results(path: Path) -> BenchmarkRun:
    """Load a BenchmarkRun from a JSON file.

    Args:
        path: Path to the JSON results file.

    Returns:
        A reconstructed BenchmarkRun instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the JSON is malformed or missing required fields.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Results file not found: {resolved}")

    text = resolved.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in '{resolved}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Results file '{resolved}' must contain a JSON object, "
            f"got {type(data).__name__}"
        )

    required_keys = {"agent_name", "results", "aggregate_score", "timestamp"}
    missing = required_keys - data.keys()
    if missing:
        raise ValueError(
            f"Results file '{resolved}' is missing required keys: {sorted(missing)}"
        )

    return _reconstruct_benchmark_run(data)


def _extract_tier(challenge_id: str) -> str:
    """Extract tier name from a challenge id like 'easy/password-gen'."""
    if "/" in challenge_id:
        return challenge_id.split("/", 1)[0]
    return "unknown"


def _bold(text: str) -> str:
    """Wrap text in Markdown bold markers."""
    return f"**{text}**"


def compare_runs(runs: list[BenchmarkRun]) -> str:
    """Generate a Markdown comparison report for multiple benchmark runs.

    Args:
        runs: List of BenchmarkRun instances to compare.

    Returns:
        A Markdown-formatted comparison report string.

    Raises:
        ValueError: If fewer than two runs are provided.
    """
    if len(runs) < 2:
        raise ValueError("At least two runs are required for comparison")

    agent_names = [run.agent_name for run in runs]
    lines: list[str] = []

    # Header
    lines.append("# AgentBench Comparison Report")
    lines.append("")
    lines.append(
        f"Comparing {len(runs)} agents: {', '.join(agent_names)}"
    )
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    header = "| Agent | Aggregate Score | Challenges Completed |"
    separator = "|-------|----------------:|---------------------:|"
    lines.append(header)
    lines.append(separator)

    for run in runs:
        completed = sum(1 for r in run.results if r.total_score > 0)
        lines.append(
            f"| {run.agent_name} | {run.aggregate_score:.1f} | {completed} |"
        )
    lines.append("")

    # Per-tier breakdown
    all_tiers: set[str] = set()
    for run in runs:
        for result in run.results:
            all_tiers.add(_extract_tier(result.challenge_id))

    if all_tiers:
        lines.append("## Per-Tier Breakdown")
        lines.append("")
        tier_header = "| Tier | " + " | ".join(agent_names) + " |"
        tier_sep = "|------|" + "|".join(
            "--------:" for _ in agent_names
        ) + "|"
        lines.append(tier_header)
        lines.append(tier_sep)

        for tier in sorted(all_tiers):
            row_parts = [f"| {tier} "]
            for run in runs:
                tier_results = [
                    r for r in run.results
                    if _extract_tier(r.challenge_id) == tier
                ]
                if tier_results:
                    avg = sum(r.total_score for r in tier_results) / len(tier_results)
                    row_parts.append(f" {avg:.1f} ")
                else:
                    row_parts.append(" - ")
            lines.append("|".join(row_parts) + "|")
        lines.append("")

    # Per-challenge detail
    all_challenge_ids: list[str] = []
    seen: set[str] = set()
    for run in runs:
        for result in run.results:
            if result.challenge_id not in seen:
                all_challenge_ids.append(result.challenge_id)
                seen.add(result.challenge_id)

    lines.append("## Per-Challenge Results")
    lines.append("")
    detail_header = "| Challenge | " + " | ".join(agent_names) + " |"
    detail_sep = "|-----------|" + "|".join(
        "--------:" for _ in agent_names
    ) + "|"
    lines.append(detail_header)
    lines.append(detail_sep)

    for cid in sorted(all_challenge_ids):
        scores: list[tuple[int, float]] = []
        for idx, run in enumerate(runs):
            matching = [r for r in run.results if r.challenge_id == cid]
            score = matching[0].total_score if matching else 0.0
            scores.append((idx, score))

        max_score = max(s for _, s in scores)
        row_parts = [f"| {cid} "]
        for idx, score in scores:
            formatted = f"{score:.1f}"
            if score == max_score and max_score > 0 and len(runs) > 1:
                # Bold the winner, but only if scores differ
                other_scores = [s for i, s in scores if i != idx]
                if any(s != max_score for s in other_scores):
                    formatted = _bold(formatted)
            row_parts.append(f" {formatted} ")
        lines.append("|".join(row_parts) + "|")

    lines.append("")

    # Methodology
    lines.append("## Methodology")
    lines.append("")
    lines.append("Scores are computed on a 0-100 scale per challenge using the ")
    lines.append("following weighted components:")
    lines.append("")
    lines.append("| Component | Weight | Description |")
    lines.append("|-----------|-------:|-------------|")
    lines.append("| Build Success | 25 | Does the project build without errors? |")
    lines.append("| Test Pass Rate | 20 | Fraction of tests passing |")
    lines.append("| Test Coverage | 15 | Line coverage percentage |")
    lines.append("| Code Quality | 15 | Based on cyclomatic complexity |")
    lines.append("| Completeness | 15 | Required files and features present |")
    lines.append("| Efficiency | 10 | Time taken relative to limit |")
    lines.append("")
    lines.append(
        "Aggregate score is the mean of all individual challenge scores."
    )
    lines.append("")
    lines.append("---")
    lines.append("*Generated by AgentBench*")

    return "\n".join(lines)


def generate_full_report(results_dir: Path) -> str:
    """Load all JSON result files from a directory and generate a comparison report.

    Args:
        results_dir: Directory containing .json result files.

    Returns:
        A Markdown comparison report string.

    Raises:
        FileNotFoundError: If the directory does not exist.
        ValueError: If fewer than two result files are found.
    """
    resolved = results_dir.resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Results directory not found: {resolved}")

    json_files = sorted(resolved.glob("*.json"))
    if not json_files:
        raise ValueError(f"No .json files found in {resolved}")

    runs = [load_results(f) for f in json_files]

    if len(runs) < 2:
        raise ValueError(
            f"Need at least 2 result files for comparison, found {len(runs)}"
        )

    return compare_runs(runs)
