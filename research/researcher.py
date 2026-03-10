"""Phase 3 Part 1 — Domain + fine-tune format research via Opus + web search."""

import asyncio
from pathlib import Path

import anthropic

from configs import load_yaml, resolve_path
from prompts.render import render


async def run() -> None:
    """Run domain research and fine-tune format research in parallel."""
    enriched_path = resolve_path("enriched_intake")
    models_path = resolve_path("models_config")
    notes_path = resolve_path("research_notes")

    with open(enriched_path) as f:
        enriched_intake = f.read()

    models_config = load_yaml(models_path)
    finetune_model = models_config["finetune_target"]["name"]

    client = anthropic.AsyncAnthropic()

    # Web search tool definition for Anthropic API
    web_search_tool = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 10,
    }

    # Domain research prompt
    domain_prompt_path = str(Path(__file__).parent.parent / "prompts" / "research" / "domain_research.md")
    with open(domain_prompt_path) as f:
        domain_system = f.read()

    # Finetune research prompt
    finetune_prompt_path = str(Path(__file__).parent.parent / "prompts" / "research" / "finetune_research.md")
    finetune_system = render(finetune_prompt_path, model_name=finetune_model)

    async def domain_research() -> str:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            temperature=0.3,
            system=domain_system,
            messages=[{"role": "user", "content": enriched_intake}],
            tools=[web_search_tool],
        )
        return _extract_text(response)

    async def finetune_research() -> str:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            temperature=0.3,
            system=finetune_system,
            messages=[{"role": "user", "content": f"Research the fine-tuning format for: {finetune_model}"}],
            tools=[web_search_tool],
        )
        return _extract_text(response)

    # Run both in parallel
    domain_result, finetune_result = await asyncio.gather(
        domain_research(),
        finetune_research(),
    )

    # Write research notes
    Path(notes_path).parent.mkdir(parents=True, exist_ok=True)
    with open(notes_path, "w") as f:
        f.write("# Research Notes\n\n")
        f.write("## Domain Research\n\n")
        f.write(domain_result + "\n\n")
        f.write("---\n\n")
        f.write("## Fine-Tune Format Research\n\n")
        f.write(finetune_result + "\n")


def _extract_text(response: anthropic.types.Message) -> str:
    """Extract text content from an Anthropic response that may contain tool use blocks."""
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts)
