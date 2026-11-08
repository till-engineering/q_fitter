"""Read config.yaml - the single place of all settings (no defaults in code)."""

from pathlib import Path

import yaml

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = PROJECT_DIR / "config.yaml"


def load_config(path: Path = CONFIG_FILE) -> dict:
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file)


def project_path(value: str) -> Path:
    """A path from the config: relative paths are relative to the project folder."""
    path = Path(value)
    return path if path.is_absolute() else PROJECT_DIR / path
