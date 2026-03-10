"""Phase 3 Part 2 — Synthesize research findings into project/ files."""

from pathlib import Path

import anthropic
import yaml

from configs import resolve_path
from pipeline.checkpoint import Checkpoint


_OUTPUT_FILES = [
    ("identity", "identity.md", "Write the identity.md file for this project."),
    ("use_cases", "use_cases.md", "Write the use_cases.md file for this project."),
    ("boundaries", "boundaries.md", "Write the boundaries.md file for this project."),
    ("persona_expert", "personas/expert.md", "Write the expert persona file for this project."),
    ("persona_beginner", "personas/beginner.md", "Write the beginner persona file for this project."),
    ("persona_adversarial", "personas/adversarial.md", "Write the adversarial persona file for this project."),
    ("topics_core", "topics/core.yaml", "Write the core topics YAML file for this project. Output valid YAML only — a list of topic strings."),
    ("topics_niches", "topics/niches.yaml", "Write the niche topics YAML file for this project. Output valid YAML only — a list of topic strings."),
]


async def run() -> None:
    """Synthesize research into project files and finetune_spec.md."""
    checkpoint = Checkpoint()
    if checkpoint.is_phase_complete(3):
        return

    notes_path = resolve_path("research_notes")
    enriched_path = resolve_path("enriched_intake")
    builder_prompt_path = str(Path(__file__).parent.parent / "prompts" / "research" / "builder.md")

    with open(notes_path) as f:
        research_notes = f.read()
    with open(enriched_path) as f:
        enriched_intake = f.read()
    with open(builder_prompt_path) as f:
        builder_system = f.read()

    context = f"## Research Notes\n\n{research_notes}\n\n## Enriched Intake\n\n{enriched_intake}"

    client = anthropic.AsyncAnthropic()
    project_dir = Path(resolve_path("identity")).parent

    # Write each project file
    for key, relative_path, instruction in _OUTPUT_FILES:
        output_path = project_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.4,
            system=builder_system,
            messages=[{"role": "user", "content": f"{context}\n\n---\n\n{instruction}"}],
        )

        content = response.content[0].text

        # For YAML files, validate the output
        if relative_path.endswith(".yaml"):
            content = _clean_yaml(content)

        with open(output_path, "w") as f:
            f.write(content)

    # Write finetune_spec.md
    finetune_spec_path = resolve_path("finetune_spec")
    instruction = (
        "Write the finetune_spec.md file for this project. "
        "This file must contain the exact chat template, all special tokens, "
        "the JSONL structure with example, system message handling, "
        "recommended max sequence length, and framework-specific notes. "
        "Use structured sections with code blocks for reliable parsing."
    )

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        temperature=0.3,
        system=builder_system,
        messages=[{"role": "user", "content": f"{context}\n\n---\n\n{instruction}"}],
    )

    Path(finetune_spec_path).parent.mkdir(parents=True, exist_ok=True)
    with open(finetune_spec_path, "w") as f:
        f.write(response.content[0].text)

    checkpoint.mark_phase_complete(3)


def _clean_yaml(content: str) -> str:
    """Extract valid YAML from LLM output that may include markdown fences."""
    # Strip markdown code fences
    lines = content.strip().split("\n")
    cleaned = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip().startswith("```"):
            cleaned.append(line)

    result = "\n".join(cleaned).strip()

    # Validate it's valid YAML
    try:
        yaml.safe_load(result)
    except yaml.YAMLError:
        pass  # Return as-is if validation fails

    return result
