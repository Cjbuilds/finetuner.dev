"""Template rendering seam. Two functions only."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent
_system_cache: dict[str, str] = {}


def render(template_path: str, **kwargs: str) -> str:
    """Read a template file and render with kwargs. Raises KeyError on missing placeholder."""
    with open(template_path) as f:
        template = f.read()
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise KeyError(f"Missing placeholder {e} in template {template_path}") from e


def render_system(role: str, **kwargs: str) -> str:
    """Read and render prompts/{role}/system.md. Cached after first call per role."""
    cache_key = role + ":" + str(sorted(kwargs.items()))
    if cache_key in _system_cache:
        return _system_cache[cache_key]

    path = _PROMPTS_DIR / role / "system.md"
    with open(path) as f:
        template = f.read()
    if kwargs:
        try:
            result = template.format(**kwargs)
        except KeyError as e:
            raise KeyError(f"Missing placeholder {e} in system prompt for {role}") from e
    else:
        result = template
    _system_cache[cache_key] = result
    return result
