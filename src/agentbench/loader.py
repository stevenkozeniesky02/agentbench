"""Challenge loader for AgentBench YAML challenge definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml

from agentbench.models import Challenge

_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset({
    "name",
    "language",
    "prompt",
    "expected_files",
    "test_commands",
    "scoring_rubric",
})

_DEFAULT_CHALLENGES_DIR: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "challenges"
)


def _validate_raw(data: dict, source: str) -> None:
    """Raise ValueError if required fields are missing from raw YAML data."""
    missing = _REQUIRED_FIELDS - data.keys()
    if missing:
        sorted_missing = sorted(missing)
        raise ValueError(
            f"Challenge file '{source}' is missing required fields: {sorted_missing}"
        )


def _build_challenge_id(path: Path) -> str:
    """Derive a challenge id like 'easy/password-gen' from the file path.

    Expects the path to sit inside a tier directory, e.g.
    challenges/easy/password-gen.yaml -> 'easy/password-gen'
    """
    return f"{path.parent.name}/{path.stem}"


def load_challenge(path: Path) -> Challenge:
    """Load a single YAML challenge file and return an immutable Challenge.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If the YAML is invalid or required fields are missing.
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Challenge file not found: {resolved}")

    text = resolved.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in '{resolved}': {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Challenge file '{resolved}' must contain a YAML mapping, "
            f"got {type(data).__name__}"
        )

    _validate_raw(data, str(resolved))

    challenge_id = data.get("id", _build_challenge_id(resolved))
    tier = data.get("tier", resolved.parent.name)

    return Challenge(
        id=challenge_id,
        name=data["name"],
        tier=tier,
        language=data["language"],
        prompt=data["prompt"],
        expected_files=list(data["expected_files"]),
        test_commands=list(data["test_commands"]),
        scoring_rubric=dict(data["scoring_rubric"]),
        time_limit_minutes=int(data.get("time_limit_minutes", 30)),
        setup_commands=list(data.get("setup_commands", [])),
    )


def load_tier(
    challenges_dir: Path | None = None,
    tier: str = "easy",
) -> list[Challenge]:
    """Load all challenges within a single tier directory.

    Args:
        challenges_dir: Root challenges directory. Defaults to the package's
            ``challenges/`` sibling directory.
        tier: The tier name (easy, medium, hard).

    Returns:
        A sorted list of Challenge objects found in the tier.

    Raises:
        FileNotFoundError: If the tier directory does not exist.
    """
    root = (challenges_dir or _DEFAULT_CHALLENGES_DIR).resolve()
    tier_dir = root / tier

    if not tier_dir.is_dir():
        raise FileNotFoundError(f"Tier directory not found: {tier_dir}")

    yaml_files = sorted(tier_dir.glob("*.yaml")) + sorted(tier_dir.glob("*.yml"))
    return [load_challenge(f) for f in yaml_files]


def load_all(challenges_dir: Path | None = None) -> list[Challenge]:
    """Load all challenges across every tier directory.

    Scans for subdirectories inside *challenges_dir* and treats each as a tier.

    Args:
        challenges_dir: Root challenges directory. Defaults to the package's
            ``challenges/`` sibling directory.

    Returns:
        A flat list of all Challenge objects, grouped by tier name.
    """
    root = (challenges_dir or _DEFAULT_CHALLENGES_DIR).resolve()

    if not root.is_dir():
        raise FileNotFoundError(f"Challenges directory not found: {root}")

    challenges: list[Challenge] = []
    for tier_dir in sorted(root.iterdir()):
        if tier_dir.is_dir():
            yaml_files = sorted(tier_dir.glob("*.yaml")) + sorted(
                tier_dir.glob("*.yml")
            )
            for f in yaml_files:
                challenges = [*challenges, load_challenge(f)]
    return challenges


def find_challenge(
    challenges_dir: Path | None = None,
    challenge_id: str = "",
) -> Challenge:
    """Find a challenge by its id (e.g. 'easy/password-gen').

    The id is interpreted as ``<tier>/<stem>`` where *stem* is the YAML
    filename without extension.

    Args:
        challenges_dir: Root challenges directory.
        challenge_id: The challenge identifier like ``easy/password-gen``.

    Returns:
        The matching Challenge.

    Raises:
        ValueError: If the id format is invalid or the challenge is not found.
    """
    if "/" not in challenge_id:
        raise ValueError(
            f"Invalid challenge id '{challenge_id}': expected format 'tier/name'"
        )

    parts = challenge_id.split("/", 1)
    tier, stem = parts[0], parts[1]

    root = (challenges_dir or _DEFAULT_CHALLENGES_DIR).resolve()
    tier_dir = root / tier

    if not tier_dir.is_dir():
        raise ValueError(
            f"Tier directory '{tier}' not found in {root}"
        )

    for ext in ("yaml", "yml"):
        candidate = tier_dir / f"{stem}.{ext}"
        if candidate.is_file():
            return load_challenge(candidate)

    raise ValueError(
        f"Challenge '{challenge_id}' not found: no file '{stem}.yaml' or "
        f"'{stem}.yml' in {tier_dir}"
    )
