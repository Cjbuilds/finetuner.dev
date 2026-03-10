"""Structured error logger. Appends JSON lines to logs/errors.jsonl."""

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

_LOGS_DIR = Path(__file__).parent
_ERRORS_FILE = _LOGS_DIR / "errors.jsonl"


def log_error(error: dict) -> None:
    """Append a structured error dict to logs/errors.jsonl with timestamp and traceback."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "module": error.get("module", "unknown"),
        "error_type": error.get("error_type", "unknown"),
        "message": error.get("message", ""),
        "traceback": error.get("traceback", traceback.format_exc() if traceback.format_exc().strip() != "NoneType: None" else ""),
    }
    _LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ERRORS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
