"""Claude Code adapter -- runs challenges via the ``claude`` CLI."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from agentbench.adapters.base import AdapterResult, AgentAdapter

logger = logging.getLogger(__name__)


class ClaudeCodeAdapter(AgentAdapter):
    """Adapter that delegates challenge execution to Claude Code (``claude -p``)."""

    @property
    def name(self) -> str:
        return "claude-code"

    def run_challenge(
        self,
        prompt: str,
        output_dir: Path,
        time_limit_minutes: int = 30,
    ) -> AdapterResult:
        """Run the challenge as a single non-interactive Claude Code invocation.

        Args:
            prompt: The full challenge prompt text.
            output_dir: Directory where Claude Code should create output files.
            time_limit_minutes: Maximum wall-clock time allowed.

        Returns:
            AdapterResult with timing, success status, and any error detail.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        full_prompt = f"{prompt}\n\nCreate all files in {output_dir}/"
        timeout_seconds = time_limit_minutes * 60

        start = time.monotonic()

        try:
            result = subprocess.run(
                ["claude", "-p", full_prompt],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed = time.monotonic() - start

            if result.returncode != 0:
                error_detail = result.stderr.strip() or result.stdout.strip()
                error_msg = f"claude exited with code {result.returncode}"
                if error_detail:
                    error_msg = f"{error_msg}: {error_detail}"
                logger.warning(error_msg)
                return AdapterResult(
                    time_taken_seconds=elapsed,
                    prompts_used=1,
                    success=False,
                    error=error_msg,
                )

            return AdapterResult(
                time_taken_seconds=elapsed,
                prompts_used=1,
                success=True,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            error_msg = (
                f"claude timed out after {time_limit_minutes} minutes"
            )
            logger.warning(error_msg)
            return AdapterResult(
                time_taken_seconds=elapsed,
                prompts_used=1,
                success=False,
                error=error_msg,
            )
        except FileNotFoundError:
            elapsed = time.monotonic() - start
            error_msg = (
                "claude CLI not found. "
                "Install it with: npm install -g @anthropic-ai/claude-code"
            )
            logger.error(error_msg)
            return AdapterResult(
                time_taken_seconds=elapsed,
                prompts_used=1,
                success=False,
                error=error_msg,
            )
        except OSError as exc:
            elapsed = time.monotonic() - start
            error_msg = f"Failed to execute claude CLI: {exc}"
            logger.error(error_msg)
            return AdapterResult(
                time_taken_seconds=elapsed,
                prompts_used=1,
                success=False,
                error=error_msg,
            )
