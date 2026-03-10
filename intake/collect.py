"""Phase 1 — Freeform project description CLI. No LLM calls."""

import sys
from pathlib import Path

from configs import resolve_path
from pipeline.checkpoint import Checkpoint


async def run() -> None:
    """Collect freeform project description from operator."""
    output_path = resolve_path("raw_intake")
    checkpoint = Checkpoint()

    if checkpoint.is_phase_complete(1):
        return

    print("\n" + "=" * 60)
    print("  PHASE 1 — Project Description")
    print("=" * 60)
    print("\nDescribe your project. What is the assistant you want to")
    print("fine-tune? What does it do? Who uses it? How should it behave?")
    print("\nType your description below. Enter an empty line to finish.\n")

    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "":
            if lines:
                break
            continue
        lines.append(line)

    if not lines:
        print("No input provided. Exiting.")
        sys.exit(1)

    description = "\n".join(lines)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(description)

    checkpoint.mark_phase_complete(1)
