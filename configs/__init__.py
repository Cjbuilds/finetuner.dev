"""Config helpers. Reads paths.yaml once and caches."""

import os
from functools import lru_cache
from pathlib import Path

import yaml

_CONFIGS_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def get_paths() -> dict[str, str]:
    """Read paths.yaml and return all paths as a dict. Cached after first call."""
    with open(_CONFIGS_DIR / "paths.yaml") as f:
        return yaml.safe_load(f)


def resolve_path(key: str) -> str:
    """Resolve a path key relative to the project root."""
    project_root = _CONFIGS_DIR.parent
    return str(project_root / get_paths()[key])


def load_yaml(path: str) -> dict:
    """Load a YAML file and return its contents."""
    with open(path) as f:
        return yaml.safe_load(f)
