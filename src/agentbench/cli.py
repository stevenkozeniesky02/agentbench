"""Click-based CLI for AgentBench with rich output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from agentbench import __version__
from agentbench.loader import find_challenge, load_all, load_tier
from agentbench.models import (
    BenchmarkRun,
    Challenge,
    ChallengeResult,
)
from agentbench.runner import run_challenge
from agentbench.report import (
    compare_runs,
    generate_full_report,
    generate_result_json,
    load_results,
    save_results,
)

console = Console()
error_console = Console(stderr=True)

# Adapter registry -- adapters register themselves here.
# Other modules populate this dict; we keep it as the single source of truth.
ADAPTERS: dict[str, type] = {}


def _get_adapter_names() -> list[str]:
    """Return sorted list of registered adapter names."""
    return sorted(ADAPTERS.keys())


def _create_adapter(name: str):
    """Instantiate an adapter by name from the registry.

    Raises:
        click.BadParameter: If the adapter name is not registered.
    """
    adapter_cls = ADAPTERS.get(name)
    if adapter_cls is None:
        available = ", ".join(_get_adapter_names()) or "(none)"
        raise click.BadParameter(
            f"Unknown agent '{name}'. Available: {available}"
        )
    return adapter_cls()


def _build_results_table(results: list[ChallengeResult]) -> Table:
    """Build a rich Table showing challenge results."""
    table = Table(title="Benchmark Results", show_lines=True)
    table.add_column("Challenge", style="cyan", no_wrap=True)
    table.add_column("Score", justify="right")
    table.add_column("Build", justify="center")
    table.add_column("Tests", justify="center")
    table.add_column("Coverage", justify="right")
    table.add_column("Time (s)", justify="right")
    table.add_column("Errors", style="dim")

    for result in results:
        sb = result.score_breakdown
        score_style = "green" if result.total_score >= 60 else (
            "yellow" if result.total_score >= 40 else "red"
        )
        build_icon = "[green]PASS[/green]" if sb.does_it_build else "[red]FAIL[/red]"
        tests_str = f"{sb.tests_passed_count}/{sb.tests_total_count}"
        tests_icon = (
            f"[green]{tests_str}[/green]" if sb.tests_pass
            else f"[red]{tests_str}[/red]"
        )
        coverage_str = f"{sb.test_coverage * 100:.0f}%"
        time_str = f"{sb.time_taken_seconds:.1f}"
        error_str = "; ".join(result.errors) if result.errors else "-"

        table.add_row(
            result.challenge_id,
            f"[{score_style}]{result.total_score:.1f}[/{score_style}]",
            build_icon,
            tests_icon,
            coverage_str,
            time_str,
            error_str,
        )

    return table


def _build_challenge_list_table(challenges: list[Challenge]) -> Table:
    """Build a rich Table listing available challenges."""
    table = Table(title="Available Challenges", show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name")
    table.add_column("Tier", justify="center")
    table.add_column("Language", justify="center")
    table.add_column("Time Limit", justify="right")

    for ch in challenges:
        tier_style = {
            "easy": "green",
            "medium": "yellow",
            "hard": "red",
        }.get(ch.tier, "white")
        table.add_row(
            ch.id,
            ch.name,
            f"[{tier_style}]{ch.tier}[/{tier_style}]",
            ch.language,
            f"{ch.time_limit_minutes}m",
        )

    return table


@click.group()
@click.version_option(version=__version__, prog_name="agentbench")
def main() -> None:
    """AgentBench: Standardized benchmark framework for comparing AI coding agents."""


@main.command()
@click.option(
    "--agent", "-a",
    required=True,
    help="Agent adapter name to benchmark.",
)
@click.option(
    "--challenge", "-c",
    "challenge_id",
    default=None,
    help="Run a specific challenge by ID (e.g. easy/password-gen).",
)
@click.option(
    "--tier", "-t",
    type=click.Choice(["easy", "medium", "hard"], case_sensitive=False),
    default=None,
    help="Run all challenges in a tier.",
)
@click.option(
    "--all", "run_all",
    is_flag=True,
    default=False,
    help="Run all available challenges.",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(path_type=Path),
    default=Path("./results"),
    show_default=True,
    help="Directory to save result JSON files.",
)
def run(
    agent: str,
    challenge_id: str | None,
    tier: str | None,
    run_all: bool,
    output_dir: Path,
) -> None:
    """Run benchmark challenges against an agent."""
    # Validate exactly one selection mode
    selection_count = sum([
        challenge_id is not None,
        tier is not None,
        run_all,
    ])
    if selection_count != 1:
        error_console.print(
            "[red]Error:[/red] Specify exactly one of --challenge, --tier, or --all."
        )
        raise SystemExit(1)

    # Resolve challenges
    try:
        if challenge_id is not None:
            challenges = [find_challenge(challenge_id=challenge_id)]
        elif tier is not None:
            challenges = load_tier(tier=tier)
        else:
            challenges = load_all()
    except (FileNotFoundError, ValueError) as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)

    if not challenges:
        error_console.print("[yellow]No challenges found.[/yellow]")
        raise SystemExit(0)

    # Create adapter
    try:
        adapter = _create_adapter(agent)
    except click.BadParameter as exc:
        error_console.print(f"[red]Error:[/red] {exc.format_message()}")
        raise SystemExit(1)

    console.print(
        f"\nRunning [bold]{len(challenges)}[/bold] challenge(s) "
        f"with agent [cyan]{agent}[/cyan]\n"
    )

    # Run with progress
    results: list[ChallengeResult] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Running challenges...", total=len(challenges))
        for ch in challenges:
            progress.update(task, description=f"Running {ch.id}...")
            result = run_challenge(adapter, ch, output_dir)
            results = [*results, result]
            progress.advance(task)

    # Compute aggregate
    aggregate = (
        sum(r.total_score for r in results) / len(results)
        if results else 0.0
    )
    now = datetime.now(timezone.utc).isoformat()

    benchmark_run = BenchmarkRun(
        agent_name=agent,
        results=results,
        aggregate_score=round(aggregate, 2),
        timestamp=now,
        metadata={"challenges_count": len(challenges)},
    )

    # Display results table
    console.print()
    console.print(_build_results_table(results))
    console.print(
        f"\n[bold]Aggregate Score:[/bold] {aggregate:.1f}/100\n"
    )

    # Save results
    output_file = output_dir / f"{agent}.json"
    saved_path = save_results(benchmark_run, output_file)
    console.print(f"Results saved to [cyan]{saved_path}[/cyan]\n")


@main.command()
@click.argument(
    "result_files",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
def compare(result_files: tuple[Path, ...]) -> None:
    """Compare two or more benchmark result JSON files."""
    if len(result_files) < 2:
        error_console.print(
            "[red]Error:[/red] Provide at least two result files to compare."
        )
        raise SystemExit(1)

    try:
        runs = [load_results(f) for f in result_files]
    except (FileNotFoundError, ValueError) as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)

    # Build rich comparison table
    agent_names = [r.agent_name for r in runs]

    # Summary table
    summary = Table(title="Agent Comparison", show_lines=True)
    summary.add_column("Agent", style="cyan")
    summary.add_column("Aggregate Score", justify="right")
    summary.add_column("Challenges", justify="right")

    for bench_run in runs:
        completed = sum(1 for r in bench_run.results if r.total_score > 0)
        score_style = "green" if bench_run.aggregate_score >= 60 else (
            "yellow" if bench_run.aggregate_score >= 40 else "red"
        )
        summary.add_row(
            bench_run.agent_name,
            f"[{score_style}]{bench_run.aggregate_score:.1f}[/{score_style}]",
            str(completed),
        )

    console.print()
    console.print(summary)

    # Detail table
    all_cids: list[str] = []
    seen: set[str] = set()
    for bench_run in runs:
        for result in bench_run.results:
            if result.challenge_id not in seen:
                all_cids.append(result.challenge_id)
                seen.add(result.challenge_id)

    detail = Table(title="Per-Challenge Scores", show_lines=True)
    detail.add_column("Challenge", style="cyan")
    for name in agent_names:
        detail.add_column(name, justify="right")

    for cid in sorted(all_cids):
        scores: list[float] = []
        for bench_run in runs:
            matching = [r for r in bench_run.results if r.challenge_id == cid]
            scores.append(matching[0].total_score if matching else 0.0)

        max_score = max(scores)
        row_values = [cid]
        for score in scores:
            style = "bold green" if (
                score == max_score and max_score > 0 and any(s != max_score for s in scores)
            ) else "white"
            row_values.append(f"[{style}]{score:.1f}[/{style}]")
        detail.add_row(*row_values)

    console.print()
    console.print(detail)
    console.print()


@main.command()
@click.argument(
    "results_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Save report to file instead of printing to stdout.",
)
def report(results_dir: Path, output: Path | None) -> None:
    """Generate a full Markdown comparison report from a results directory."""
    try:
        markdown = generate_full_report(results_dir)
    except (FileNotFoundError, ValueError) as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)

    if output is not None:
        resolved = output.resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(markdown, encoding="utf-8")
        console.print(f"Report saved to [cyan]{resolved}[/cyan]")
    else:
        console.print(markdown)


@main.command(name="list")
def list_challenges() -> None:
    """List all available benchmark challenges."""
    try:
        challenges = load_all()
    except FileNotFoundError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise SystemExit(1)

    if not challenges:
        console.print("[yellow]No challenges found.[/yellow]")
        return

    console.print()
    console.print(_build_challenge_list_table(challenges))
    console.print(f"\n[dim]{len(challenges)} challenge(s) available[/dim]\n")
