"""Code-quality metric for AgentBench."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_QUALITY_TIMEOUT_SECONDS = 120

_DEFAULT_COMPLEXITY = 5.0

_LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py",),
    "typescript": (".ts", ".js"),
    "go": (".go",),
    "rust": (".rs",),
}

_RADON_AVG_PATTERN = re.compile(r"Average complexity:\s*[A-F]?\s*\(?([\d.]+)\)?")


def _count_files(output_dir: Path, extensions: tuple[str, ...]) -> list[Path]:
    """Collect source files matching the given extensions."""
    files: list[Path] = []
    try:
        for ext in extensions:
            files.extend(output_dir.rglob(f"*{ext}"))
    except OSError as exc:
        logger.warning("Error scanning files in %s: %s", output_dir, exc)
    return files


def _average_file_size(files: list[Path]) -> float:
    """Return average line count across *files*."""
    if not files:
        return 0.0

    total_lines = 0
    counted = 0
    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            total_lines += content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            counted += 1
        except OSError:
            continue

    return total_lines / counted if counted > 0 else 0.0


def _python_complexity(output_dir: Path) -> float:
    """Use radon to compute average cyclomatic complexity for Python code."""
    try:
        result = subprocess.run(
            f"radon cc -a -nc {output_dir}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=_QUALITY_TIMEOUT_SECONDS,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        match = _RADON_AVG_PATTERN.search(combined)
        if match:
            return float(match.group(1))
    except subprocess.TimeoutExpired:
        logger.warning("Radon timed out after %ds", _QUALITY_TIMEOUT_SECONDS)
    except OSError as exc:
        logger.warning("Failed to run radon: %s", exc)
    except ValueError:
        pass

    return _DEFAULT_COMPLEXITY


def measure_quality(output_dir: Path, language: str) -> dict[str, Any]:
    """Compute basic code-quality metrics for a project.

    Args:
        output_dir: Project root directory.
        language: One of ``"python"``, ``"typescript"``, ``"go"``, ``"rust"``.

    Returns:
        A dictionary with keys ``file_count``, ``avg_file_size``, and
        ``avg_complexity``.
    """
    language = language.lower()

    extensions = _LANGUAGE_EXTENSIONS.get(language, ())
    if not extensions:
        logger.warning("Unsupported language for quality metrics: %s", language)
        return {"file_count": 0, "avg_file_size": 0.0, "avg_complexity": 0.0}

    files = _count_files(output_dir, extensions)
    file_count = len(files)
    avg_file_size = _average_file_size(files)

    if language == "python":
        avg_complexity = _python_complexity(output_dir)
    else:
        avg_complexity = _DEFAULT_COMPLEXITY

    return {
        "file_count": file_count,
        "avg_file_size": avg_file_size,
        "avg_complexity": avg_complexity,
    }
