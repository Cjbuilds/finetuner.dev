"""User role client. Wraps AsyncAnthropic to generate user turns."""

import asyncio

import anthropic

from configs import load_yaml, resolve_path
from prompts.render import render, render_system


class UserClient:
    def __init__(self) -> None:
        models_config = load_yaml(resolve_path("models_config"))
        self._model = models_config["user_model"]["name"]
        self._temperature = models_config["user_model"]["temperature"]
        self._max_tokens = models_config["user_model"]["max_tokens"]
        self._system_prompt = render_system("user")
        from pathlib import Path
        self._task_template = str(Path(__file__).parent.parent / "prompts" / "user" / "task.md")

        dataset_config = load_yaml(resolve_path("dataset_config"))
        self._max_retries = dataset_config["max_retries"]

        self._client = anthropic.AsyncAnthropic()

    async def generate_user_turn(
        self,
        persona: str,
        topic: str,
        niches: str,
        history: list[dict],
    ) -> str:
        """Generate a single user turn. Returns the content string."""
        history_text = ""
        if history:
            lines = []
            for msg in history:
                lines.append(f"{msg['role'].upper()}: {msg['content']}")
            history_text = "\n\n".join(lines)

        task_content = render(
            self._task_template,
            persona=persona,
            topic=topic,
            niches=niches,
            history=history_text,
        )

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    temperature=self._temperature,
                    system=self._system_prompt,
                    messages=[{"role": "user", "content": task_content}],
                )
                return response.content[0].text
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise last_error
