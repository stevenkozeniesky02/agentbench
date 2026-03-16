"""Tests for agentbench.loader -- YAML challenge loading and discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentbench.loader import (
    find_challenge,
    load_all,
    load_challenge,
    load_tier,
)
from agentbench.models import Challenge


# ---------------------------------------------------------------------------
# load_challenge
# ---------------------------------------------------------------------------


class TestLoadChallenge:

    def test_loads_valid_yaml(self, tmp_challenges: Path) -> None:
        path = tmp_challenges / "easy" / "password-gen.yaml"
        challenge = load_challenge(path)

        assert isinstance(challenge, Challenge)
        assert challenge.name == "Password Generator"
        assert challenge.tier == "easy"
        assert challenge.language == "python"
        assert challenge.prompt == "Build a password generator CLI."
        assert challenge.expected_files == ["main.py", "tests/test_main.py"]
        assert challenge.test_commands == ["pytest"]
        assert challenge.time_limit_minutes == 20
        assert challenge.setup_commands == ["pip install -e ."]

    def test_derives_id_from_path(self, tmp_challenges: Path) -> None:
        path = tmp_challenges / "easy" / "password-gen.yaml"
        challenge = load_challenge(path)
        assert challenge.id == "easy/password-gen"

    def test_explicit_id_overrides_derived(self, tmp_path: Path) -> None:
        data = {
            "id": "custom/my-id",
            "name": "Custom",
            "tier": "easy",
            "language": "python",
            "prompt": "Do something.",
            "expected_files": ["x.py"],
            "test_commands": ["pytest"],
            "scoring_rubric": {"a": 1},
        }
        tier_dir = tmp_path / "easy"
        tier_dir.mkdir()
        fpath = tier_dir / "custom.yaml"
        fpath.write_text(yaml.dump(data), encoding="utf-8")
        challenge = load_challenge(fpath)
        assert challenge.id == "custom/my-id"

    def test_default_time_limit(self, tmp_path: Path) -> None:
        data = {
            "name": "Minimal",
            "tier": "easy",
            "language": "python",
            "prompt": "Do it.",
            "expected_files": [],
            "test_commands": [],
            "scoring_rubric": {},
        }
        tier_dir = tmp_path / "easy"
        tier_dir.mkdir()
        fpath = tier_dir / "minimal.yaml"
        fpath.write_text(yaml.dump(data), encoding="utf-8")
        challenge = load_challenge(fpath)
        assert challenge.time_limit_minutes == 30

    def test_missing_required_fields_raises_value_error(self, tmp_path: Path) -> None:
        incomplete = {"name": "Incomplete", "tier": "easy"}
        tier_dir = tmp_path / "easy"
        tier_dir.mkdir()
        fpath = tier_dir / "bad.yaml"
        fpath.write_text(yaml.dump(incomplete), encoding="utf-8")

        with pytest.raises(ValueError, match="missing required fields"):
            load_challenge(fpath)

    def test_nonexistent_file_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_challenge(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises_value_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{{{{invalid yaml: [", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_challenge(bad_file)

    def test_non_mapping_yaml_raises_value_error(self, tmp_path: Path) -> None:
        list_file = tmp_path / "list.yaml"
        list_file.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ValueError, match="must contain a YAML mapping"):
            load_challenge(list_file)


# ---------------------------------------------------------------------------
# load_tier
# ---------------------------------------------------------------------------


class TestLoadTier:

    def test_loads_all_yaml_and_yml_from_tier(self, tmp_challenges: Path) -> None:
        challenges = load_tier(challenges_dir=tmp_challenges, tier="easy")
        assert len(challenges) == 2
        names = {c.name for c in challenges}
        assert "Password Generator" in names
        assert "URL Shortener" in names

    def test_loads_medium_tier(self, tmp_challenges: Path) -> None:
        challenges = load_tier(challenges_dir=tmp_challenges, tier="medium")
        assert len(challenges) == 1
        assert challenges[0].name == "REST API"

    def test_nonexistent_tier_raises_file_not_found(self, tmp_challenges: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Tier directory not found"):
            load_tier(challenges_dir=tmp_challenges, tier="impossible")

    def test_empty_tier_returns_empty_list(self, tmp_path: Path) -> None:
        empty_tier = tmp_path / "challenges" / "empty"
        empty_tier.mkdir(parents=True)
        challenges = load_tier(challenges_dir=tmp_path / "challenges", tier="empty")
        assert challenges == []


# ---------------------------------------------------------------------------
# load_all
# ---------------------------------------------------------------------------


class TestLoadAll:

    def test_loads_from_all_tiers(self, tmp_challenges: Path) -> None:
        challenges = load_all(challenges_dir=tmp_challenges)
        # easy has 2 files, medium has 1
        assert len(challenges) == 3

    def test_nonexistent_dir_raises_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_all(challenges_dir=tmp_path / "nope")

    def test_empty_root_returns_empty_list(self, tmp_path: Path) -> None:
        root = tmp_path / "challenges"
        root.mkdir()
        challenges = load_all(challenges_dir=root)
        assert challenges == []


# ---------------------------------------------------------------------------
# find_challenge
# ---------------------------------------------------------------------------


class TestFindChallenge:

    def test_finds_yaml_by_id(self, tmp_challenges: Path) -> None:
        challenge = find_challenge(
            challenges_dir=tmp_challenges, challenge_id="easy/password-gen"
        )
        assert challenge.name == "Password Generator"

    def test_finds_yml_by_id(self, tmp_challenges: Path) -> None:
        challenge = find_challenge(
            challenges_dir=tmp_challenges, challenge_id="easy/url-shortener"
        )
        assert challenge.name == "URL Shortener"

    def test_invalid_id_format_raises_value_error(self, tmp_challenges: Path) -> None:
        with pytest.raises(ValueError, match="expected format"):
            find_challenge(challenges_dir=tmp_challenges, challenge_id="noslash")

    def test_nonexistent_tier_raises_value_error(self, tmp_challenges: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            find_challenge(challenges_dir=tmp_challenges, challenge_id="hard/thing")

    def test_nonexistent_challenge_raises_value_error(self, tmp_challenges: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            find_challenge(
                challenges_dir=tmp_challenges, challenge_id="easy/nonexistent"
            )
