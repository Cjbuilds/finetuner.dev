"""Validator role client. Wraps AsyncAnthropic for validation and scoring."""

import asyncio
import json
from pathlib import Path

import anthropic

from configs import load_yaml, resolve_path
from data_types import Sample, ScoreOutput, ValidatorOutput
from prompts.render import render, render_system


class ValidatorClient:
    def __init__(self) -> None:
        models_config = load_yaml(resolve_path("models_config"))
        validator_cfg = models_config["validator_model"]
        self._model = validator_cfg["name"]
        self._temperature = validator_cfg["temperature"]
        self._max_tokens = validator_cfg["max_tokens"]
        self._system_prompt = render_system("validator")

        dataset_config = load_yaml(resolve_path("dataset_config"))
        self._max_retries = dataset_config["max_retries"]

        self._client = anthropic.AsyncAnthropic()

        self._validate_template = str(
            Path(__file__).parent.parent / "prompts" / "validator" / "task.md"
        )
        self._score_template = str(
            Path(__file__).parent.parent / "prompts" / "validator" / "score_task.md"
        )

    async def validate(self, teacher_system: str, sample: Sample) -> ValidatorOutput:
        """Binary validate a sample. Returns ValidatorOutput."""
        sample_json = json.dumps({
            "user_turn": sample.user_turn,
            "assistant_response": sample.accepted_response,
            "topic": sample.topic,
            "persona": sample.persona,
        }, indent=2)

        task_content = render(
            self._validate_template,
            teacher_system=teacher_system,
            sample=sample_json,
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
                text = response.content[0].text.strip()
                # Extract JSON from response
                data = json.loads(self._extract_json(text))
                return ValidatorOutput(
                    accepted=data["accepted"],
                    reason=data["reason"],
                )
            except (json.JSONDecodeError, KeyError) as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise last_error

    async def score(self, sample: Sample) -> ScoreOutput:
        """Score a sample 1-10. Returns ScoreOutput."""
        sample_json = json.dumps({
            "user_turn": sample.user_turn,
            "assistant_response": sample.accepted_response,
            "topic": sample.topic,
            "persona": sample.persona,
        }, indent=2)

        task_content = render(
            self._score_template,
            sample=sample_json,
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
                text = response.content[0].text.strip()
                data = json.loads(self._extract_json(text))
                return ScoreOutput(
                    score=float(data["score"]),
                    reason=data["reason"],
                )
            except (json.JSONDecodeError, KeyError) as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise last_error

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract JSON object from text that may have surrounding content."""
        # Try the raw text first
        text = text.strip()
        if text.startswith("{"):
            return text
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return text[start:end + 1]
        return text
