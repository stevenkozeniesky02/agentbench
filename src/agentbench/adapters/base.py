"""Base adapter interface for AgentBench agent integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdapterResult:
    """Immutable result returned by an agent adapter after running a challenge."""

    time_taken_seconds: float
    prompts_used: int
    success: bool
    error: str | None = None


class AgentAdapter(ABC):
    """Base class for agent adapters that execute challenges."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""
        ...

    @abstractmethod
    def run_challenge(
        self,
        prompt: str,
        output_dir: Path,
        time_limit_minutes: int = 30,
    ) -> AdapterResult:
        """Run a challenge prompt and produce output in output_dir.

        Args:
            prompt: The full challenge prompt text.
            output_dir: Directory where the agent should create output files.
            time_limit_minutes: Maximum wall-clock time allowed.

        Returns:
            AdapterResult with timing and metadata.
        """
        ...
