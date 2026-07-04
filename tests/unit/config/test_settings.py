"""Tests for searchat.config.settings edge cases."""
from __future__ import annotations

from pathlib import Path

import pytest

from searchat.config import Config


class TestConfigLoad:
    """Tests for Config.load edge cases."""

    def test_explicit_missing_path_raises(self, tmp_path):
        """Config.load with explicit nonexistent path raises FileNotFoundError."""
        missing = tmp_path / "nonexistent" / "settings.toml"
        with pytest.raises(FileNotFoundError):
            Config.load(config_path=missing)

    def test_default_load_succeeds(self):
        """Config.load without explicit path falls back to defaults."""
        config = Config.load()
        assert config is not None
        assert config.paths is not None


class TestRetentionConfig:
    """Tests for `RetentionConfig` (M12): per-project retention policy
    schema, validation, and the fail-closed contract for malformed
    blocks.
    """

    def test_no_project_blocks_resolves_to_none_for_any_project(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict({})
        assert config.resolve("any-project") is None

    def test_resolve_with_none_project_id_returns_none(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"never_touch": True}}}
        )
        assert config.resolve(None) is None
        assert config.resolve("") is None

    def test_project_override_parses_all_fields(self) -> None:
        from searchat.config.settings import ProjectRetentionPolicy, RetentionConfig

        config = RetentionConfig.from_dict(
            {
                "project": {
                    "proj-a": {
                        "never_touch": False,
                        "archive_after_days": 90,
                        "distill_after_days": 365,
                    }
                }
            }
        )
        policy = config.resolve("proj-a")
        assert policy == ProjectRetentionPolicy(
            never_touch=False, archive_after_days=90, distill_after_days=365
        )

    def test_project_not_configured_resolves_to_none(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"never_touch": True}}}
        )
        assert config.resolve("proj-b") is None

    def test_never_touch_project_resolves_never_touch_true(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"never_touch": True}}}
        )
        policy = config.resolve("proj-a")
        assert policy is not None
        assert policy.never_touch is True

    def test_malformed_block_unknown_key_fails_closed_to_never_touch(self) -> None:
        """An unrecognized key is ambiguous -- M12's contract is that this
        resolves to never_touch=True, never to silently dropping the
        unknown key and falling through to the global default."""
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"archive_after_dyas": 30}}}
        )
        policy = config.resolve("proj-a")
        assert policy is not None
        assert policy.never_touch is True

    def test_malformed_block_non_bool_never_touch_fails_closed(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"never_touch": "yes"}}}
        )
        policy = config.resolve("proj-a")
        assert policy is not None
        assert policy.never_touch is True

    def test_malformed_block_negative_day_count_fails_closed(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"archive_after_days": -1}}}
        )
        policy = config.resolve("proj-a")
        assert policy is not None
        assert policy.never_touch is True

    def test_malformed_block_non_integer_day_count_fails_closed(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {"project": {"proj-a": {"distill_after_days": "soon"}}}
        )
        policy = config.resolve("proj-a")
        assert policy is not None
        assert policy.never_touch is True

    def test_malformed_block_not_a_table_fails_closed(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict({"project": {"proj-a": "not-a-table"}})
        policy = config.resolve("proj-a")
        assert policy is not None
        assert policy.never_touch is True

    def test_non_dict_project_section_yields_empty_config(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict({"project": "not-a-table"})
        assert config.resolve("proj-a") is None

    def test_two_projects_with_independent_overrides(self) -> None:
        """Fixture matching M12's acceptance criterion: two projects on
        different thresholds, independently resolved."""
        from searchat.config.settings import RetentionConfig

        config = RetentionConfig.from_dict(
            {
                "project": {
                    "proj-fast": {"distill_after_days": 7},
                    "proj-slow": {"distill_after_days": 400},
                }
            }
        )
        assert config.resolve("proj-fast").distill_after_days == 7
        assert config.resolve("proj-slow").distill_after_days == 400

    def test_config_load_includes_retention_section(self) -> None:
        from searchat.config.settings import RetentionConfig

        config = Config.load()
        assert isinstance(config.retention, RetentionConfig)
        assert config.retention.resolve("any-project") is None
