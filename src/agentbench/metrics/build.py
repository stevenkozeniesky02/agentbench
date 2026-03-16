"""Build verification metric for AgentBench."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILD_TIMEOUT_SECONDS = 120


def check_build(
    output_dir: Path,
    setup_commands: list[str],
) -> tuple[bool, list[str]]:
    """Run build/setup commands and report whether they all succeed.

    Args:
        output_dir: Working directory in which to execute commands.
        setup_commands: Shell commands to run (e.g. ``pip install -e .``).

    Returns:
        A tuple of ``(success, errors)`` where *success* is ``True`` only
        when every command exits with code 0, and *errors* collects stderr
        output from any failing command.
    """
    if not setup_commands:
        return (True, [])

    errors: list[str] = []

    for command in setup_commands:
        try:
            result = subprocess.run(
                command,
                # shell=True is intentional: setup_commands are shell command
                # strings defined in challenge YAML files (trusted input), not
                # user-supplied input.  They may contain pipes, redirects, and
                # other shell syntax that require a shell interpreter.
                shell=True,
                cwd=str(output_dir),
                capture_output=True,
                text=True,
                timeout=_BUILD_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip()
                msg = f"Command failed (exit {result.returncode}): {command}"
                if detail:
                    msg = f"{msg}\n{detail}"
                errors.append(msg)
                logger.warning(msg)
        except subprocess.TimeoutExpired:
            msg = f"Command timed out after {_BUILD_TIMEOUT_SECONDS}s: {command}"
            errors.append(msg)
            logger.warning(msg)
        except OSError as exc:
            msg = f"Failed to execute command: {command} ({exc})"
            errors.append(msg)
            logger.warning(msg)

    success = len(errors) == 0
    return (success, errors)
