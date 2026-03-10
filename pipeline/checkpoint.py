"""Crash-safe checkpoint tracking. Atomic writes via temp file + rename."""

import json
import os
from pathlib import Path

from configs import resolve_path
from data_types import CheckpointState


class Checkpoint:
    def __init__(self) -> None:
        self._path = resolve_path("checkpoint")
        self._state = self._load()

    def _load(self) -> CheckpointState:
        if os.path.exists(self._path):
            with open(self._path) as f:
                data = json.load(f)
            return CheckpointState(**data)
        return CheckpointState()

    def _save(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(self._state.model_dump(), f, indent=2)
        os.replace(tmp_path, self._path)

    def mark_phase_complete(self, phase: int) -> None:
        field = f"phase_{phase}_complete"
        setattr(self._state, field, True)
        self._save()

    def is_phase_complete(self, phase: int) -> bool:
        field = f"phase_{phase}_complete"
        return getattr(self._state, field)

    def update_counts(self, single: int, multi: int) -> None:
        self._state.single_completed = single
        self._state.multi_completed = multi
        self._save()

    def get_counts(self) -> tuple[int, int]:
        return self._state.single_completed, self._state.multi_completed
