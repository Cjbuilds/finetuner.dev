"""Phase 2 — Gap analysis, question generation, model selection. Writes models.yaml."""

import os
import re
from pathlib import Path

import anthropic
import yaml

from configs import load_yaml, resolve_path
from pipeline.checkpoint import Checkpoint
from prompts.render import render_system


async def run() -> None:
    """Run gap analysis and collect answers from operator."""
    checkpoint = Checkpoint()
    if checkpoint.is_phase_complete(2):
        return

    raw_intake_path = resolve_path("raw_intake")
    enriched_path = resolve_path("enriched_intake")
    models_path = resolve_path("models_config")

    with open(raw_intake_path) as f:
        raw_intake = f.read()

    client = anthropic.AsyncAnthropic()

    # Call 1 — Gap Analysis
    gap_system = str(Path(__file__).parent.parent / "prompts" / "intake" / "gap_analysis.md")
    with open(gap_system) as f:
        gap_system_prompt = f.read()

    print("\n  Analyzing your project description...")

    gap_response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.3,
        system=gap_system_prompt,
        messages=[{"role": "user", "content": raw_intake}],
    )
    gap_analysis = gap_response.content[0].text

    # Call 2 — Question Generation
    questions_system = str(Path(__file__).parent.parent / "prompts" / "intake" / "questions.md")
    with open(questions_system) as f:
        questions_system_prompt = f.read()

    questions_response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        temperature=0.3,
        system=questions_system_prompt,
        messages=[{"role": "user", "content": gap_analysis}],
    )
    questions_text = questions_response.content[0].text

    # Parse questions (numbered lines)
    questions = []
    for line in questions_text.strip().split("\n"):
        line = line.strip()
        if line and line[0].isdigit():
            # Remove number prefix
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
            if cleaned:
                questions.append(cleaned)

    if not questions:
        questions = [questions_text.strip()]

    # Present questions one at a time
    print("\n" + "=" * 60)
    print("  PHASE 2 — Follow-up Questions")
    print("=" * 60)
    print(f"\n  {len(questions)} questions to answer.\n")

    qa_pairs: list[tuple[str, str]] = []
    model_answers: dict[str, str] = {}

    for i, question in enumerate(questions, 1):
        print(f"  Q{i}: {question}")
        print()
        answer = input("  A: ").strip()
        print()
        qa_pairs.append((question, answer))

        # Detect model selection questions
        q_lower = question.lower()
        if "user turn" in q_lower or "question-asker" in q_lower or "question asker" in q_lower:
            model_answers["user_model"] = answer
        elif "teacher" in q_lower and ("ideal response" in q_lower or "together ai" in q_lower or "generates" in q_lower):
            model_answers["teacher_model"] = answer
        elif "validate" in q_lower and "score" in q_lower:
            model_answers["validator_model"] = answer
        elif "fine-tun" in q_lower and ("format" in q_lower or "output" in q_lower or "are you" in q_lower):
            model_answers["finetune_target"] = answer

    # Write enriched intake
    Path(enriched_path).parent.mkdir(parents=True, exist_ok=True)
    with open(enriched_path, "w") as f:
        f.write("# Enriched Intake\n\n")
        f.write("## Original Project Description\n\n")
        f.write(raw_intake + "\n\n")
        f.write("## Follow-up Questions & Answers\n\n")
        for q, a in qa_pairs:
            f.write(f"**Q:** {q}\n")
            f.write(f"**A:** {a}\n\n")

    # Write models.yaml if it doesn't already exist
    if not os.path.exists(models_path) or os.path.getsize(models_path) == 0:
        models_data = {
            "user_model": {
                "name": model_answers.get("user_model", "claude-haiku-4-5-20251001"),
                "temperature": 0.9,
                "max_tokens": 1024,
            },
            "teacher_model": {
                "name": model_answers.get("teacher_model", "Qwen/Qwen3-235B-A22B"),
                "temperature": 0.7,
                "max_tokens": 4096,
                "thinking_tokens": "disabled",
            },
            "validator_model": {
                "name": model_answers.get("validator_model", "claude-haiku-4-5-20251001"),
                "temperature": 0.1,
                "max_tokens": 512,
            },
            "finetune_target": {
                "name": model_answers.get("finetune_target", "Qwen/Qwen3-30B-A3B"),
            },
            "dedup_model": "all-MiniLM-L6-v2",
        }

        Path(models_path).parent.mkdir(parents=True, exist_ok=True)
        with open(models_path, "w") as f:
            yaml.dump(models_data, f, default_flow_style=False, sort_keys=False)

    checkpoint.mark_phase_complete(2)
