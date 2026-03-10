"""Teacher role client. Wraps AsyncOpenAI pointed at Together AI."""

import asyncio
import re
from pathlib import Path

from openai import AsyncOpenAI

from configs import load_yaml, resolve_path
from data_types import Message, TokenUsage
from tools.calculator import calculate
from tools.web_search import search as web_search


class TeacherClient:
    def __init__(self) -> None:
        models_config = load_yaml(resolve_path("models_config"))
        teacher_cfg = models_config["teacher_model"]
        self._model = teacher_cfg["name"]
        self._temperature = teacher_cfg["temperature"]
        self._max_tokens = teacher_cfg["max_tokens"]
        self._thinking_tokens = teacher_cfg.get("thinking_tokens", "disabled")

        tools_config = load_yaml(resolve_path("tools_config"))
        self._use_calculator = tools_config["use_calculator"]
        self._use_web_search = tools_config["use_web_search"]
        self._max_tool_calls = tools_config["max_tool_calls_per_sample"]

        dataset_config = load_yaml(resolve_path("dataset_config"))
        self._max_retries = dataset_config["max_retries"]

        import os
        self._client = AsyncOpenAI(
            api_key=os.environ.get("TOGETHER_API_KEY", ""),
            base_url="https://api.together.xyz/v1",
        )

        self._system_prompt = ""

    def set_system_prompt(self, system_prompt: str) -> None:
        """Set the cached system prompt. Called once at pipeline init."""
        self._system_prompt = system_prompt

    def _build_tools(self) -> list[dict] | None:
        tools = []
        if self._use_calculator:
            tools.append({
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Evaluate a mathematical expression safely. Supports arithmetic, sqrt, log, trig functions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "The mathematical expression to evaluate, e.g. '2 + 3 * 4' or 'sqrt(16)'",
                            }
                        },
                        "required": ["expression"],
                    },
                },
            })
        if self._use_web_search:
            tools.append({
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information. Returns titles, URLs, and snippets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query",
                            },
                            "num_results": {
                                "type": "integer",
                                "description": "Number of results to return (default 5)",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                },
            })
        return tools if tools else None

    async def _execute_tool(self, name: str, arguments: dict) -> str:
        """Execute a tool call and return the result string."""
        if name == "calculate":
            return calculate(arguments.get("expression", ""))
        if name == "web_search":
            import json
            results = await web_search(
                arguments.get("query", ""),
                arguments.get("num_results", 5),
            )
            return json.dumps(results)
        return f"Error: Unknown tool '{name}'"

    def _strip_thinking(self, text: str) -> str:
        """Strip <think>...</think> tags from response."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def complete(self, messages: list[Message]) -> tuple[str, TokenUsage]:
        """Generate a teacher response. Handles tool calls. Returns (response, token_usage)."""
        openai_messages = [{"role": "system", "content": self._system_prompt}]
        for msg in messages:
            openai_messages.append({"role": msg.role, "content": msg.content})

        tools = self._build_tools()
        total_input = 0
        total_output = 0
        tool_calls_made = 0

        extra_body = {}
        if self._thinking_tokens == "disabled":
            extra_body["chat_template_kwargs"] = {"enable_thinking": False}

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                kwargs: dict = {
                    "model": self._model,
                    "messages": openai_messages,
                    "max_tokens": self._max_tokens,
                    "temperature": self._temperature,
                }
                if tools:
                    kwargs["tools"] = tools
                if extra_body:
                    kwargs["extra_body"] = extra_body

                response = await self._client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                last_error = e
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise last_error

        total_input += response.usage.prompt_tokens if response.usage else 0
        total_output += response.usage.completion_tokens if response.usage else 0

        # Tool call resolution loop
        while (
            response.choices[0].message.tool_calls
            and tool_calls_made < self._max_tool_calls
        ):
            assistant_message = response.choices[0].message
            openai_messages.append(assistant_message.model_dump())

            for tool_call in assistant_message.tool_calls:
                tool_calls_made += 1
                import json
                args = json.loads(tool_call.function.arguments) if isinstance(
                    tool_call.function.arguments, str
                ) else tool_call.function.arguments

                result = await self._execute_tool(tool_call.function.name, args)
                openai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # Follow-up call after tool results
            for attempt in range(self._max_retries):
                try:
                    kwargs = {
                        "model": self._model,
                        "messages": openai_messages,
                        "max_tokens": self._max_tokens,
                        "temperature": self._temperature,
                    }
                    if tools:
                        kwargs["tools"] = tools
                    if extra_body:
                        kwargs["extra_body"] = extra_body

                    response = await self._client.chat.completions.create(**kwargs)
                    break
                except Exception as e:
                    last_error = e
                    if attempt < self._max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        raise last_error

            total_input += response.usage.prompt_tokens if response.usage else 0
            total_output += response.usage.completion_tokens if response.usage else 0

        content = response.choices[0].message.content or ""
        if self._thinking_tokens == "strip":
            content = self._strip_thinking(content)

        usage = TokenUsage(
            role="teacher",
            input_tokens=total_input,
            output_tokens=total_output,
        )
        return content, usage
