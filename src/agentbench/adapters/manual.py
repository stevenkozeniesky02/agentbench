"""Manual adapter -- delegates challenge execution to a human operator."""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from agentbench.adapters.base import AdapterResult, AgentAdapter

_console = Console()


class ManualAdapter(AgentAdapter):
    """Adapter that prints the prompt and waits for a human to complete the challenge."""

    @property
    def name(self) -> str:
        return "manual"

    def run_challenge(
        self,
        prompt: str,
        output_dir: Path,
        time_limit_minutes: int = 30,
    ) -> AdapterResult:
        """Display the prompt, wait for the human, and record wall-clock time.

        The operator is expected to use an agent of their choice (or work
        manually) and place all output files into *output_dir*.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        _console.print(
            Panel(
                prompt,
                title="[bold cyan]Challenge Prompt[/bold cyan]",
                expand=False,
            )
        )
        _console.print(
            f"\n[yellow]Place your output files in:[/yellow] {output_dir}"
        )
        _console.print(
            f"[yellow]Time limit:[/yellow] {time_limit_minutes} minutes\n"
        )

        start = time.monotonic()

        try:
            input("Press Enter when you are done...")
        except (EOFError, KeyboardInterrupt):
            elapsed = time.monotonic() - start
            return AdapterResult(
                time_taken_seconds=elapsed,
                prompts_used=0,
                success=False,
                error="User interrupted the challenge.",
            )

        elapsed = time.monotonic() - start

        prompts_used = _ask_prompts_used()

        return AdapterResult(
            time_taken_seconds=elapsed,
            prompts_used=prompts_used,
            success=True,
        )


def _ask_prompts_used() -> int:
    """Prompt the operator for the number of interventions they used."""
    while True:
        raw = input("How many prompts/interventions did you use? ").strip()
        try:
            value = int(raw)
            if value < 0:
                _console.print("[red]Please enter a non-negative integer.[/red]")
                continue
            return value
        except ValueError:
            _console.print("[red]Please enter a valid integer.[/red]")
