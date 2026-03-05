"""User configuration from ~/.gaia/config.toml."""

from pathlib import Path

import tomllib


DEFAULT_CONFIG = {
    "review": {
        "model": "claude-sonnet-4-20250514",
        "concurrency": 5,
        "skill_version": "v1.0",
    },
}


def load_user_config() -> dict:
    """Load user config from ~/.gaia/config.toml, with defaults."""
    config_path = Path.home() / ".gaia" / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            user = tomllib.load(f)
        merged = {**DEFAULT_CONFIG}
        for key, val in user.items():
            if isinstance(val, dict) and key in merged:
                merged[key] = {**merged[key], **val}
            else:
                merged[key] = val
        return merged
    return DEFAULT_CONFIG
