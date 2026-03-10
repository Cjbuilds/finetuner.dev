"""Export accepted samples to final train/eval JSONL. Format driven by finetune_spec.md."""

import json
import os
import random
import re
from pathlib import Path

from configs import load_yaml, resolve_path


def export(state: object) -> None:
    """Read finetune_spec.md, format accepted samples, write train.jsonl + eval.jsonl."""
    dataset_config = load_yaml(resolve_path("dataset_config"))
    eval_split = dataset_config["eval_split"]
    shuffle_seed = dataset_config["shuffle_seed"]

    accepted_path = resolve_path("accepted_samples")
    train_path = resolve_path("train_output")
    eval_path = resolve_path("eval_output")
    stats_path = resolve_path("stats")
    finetune_spec_path = resolve_path("finetune_spec")

    # Read finetune spec
    with open(finetune_spec_path) as f:
        spec_content = f.read()

    # Parse format specification from finetune_spec.md
    format_info = _parse_spec(spec_content)

    # Read accepted samples
    if not os.path.exists(accepted_path):
        return

    with open(accepted_path) as f:
        samples = [json.loads(line) for line in f if line.strip()]

    if not samples:
        return

    # Shuffle
    random.seed(shuffle_seed)
    random.shuffle(samples)

    # Split
    eval_count = max(1, int(len(samples) * eval_split))
    eval_samples = samples[:eval_count]
    train_samples = samples[eval_count:]

    # Format and write
    Path(train_path).parent.mkdir(parents=True, exist_ok=True)
    Path(eval_path).parent.mkdir(parents=True, exist_ok=True)

    with open(train_path, "w") as f:
        for sample in train_samples:
            formatted = _format_sample(sample, format_info)
            f.write(json.dumps(formatted) + "\n")

    with open(eval_path, "w") as f:
        for sample in eval_samples:
            formatted = _format_sample(sample, format_info)
            f.write(json.dumps(formatted) + "\n")

    # Write stats
    stats = {
        "total_accepted": len(samples),
        "train_count": len(train_samples),
        "eval_count": len(eval_samples),
        "single_count": sum(1 for s in samples if s.get("kind") == "single"),
        "multi_count": sum(1 for s in samples if s.get("kind") == "multi"),
        "acceptance_rate": state.acceptance_rate if hasattr(state, "acceptance_rate") else 0.0,
        "score_buckets": state.score_buckets if hasattr(state, "score_buckets") else {},
    }

    Path(stats_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = stats_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(stats, f, indent=2)
    os.replace(tmp_path, stats_path)


def _parse_spec(spec_content: str) -> dict:
    """Parse finetune_spec.md for format information."""
    info: dict = {
        "role_mapping": {"user": "user", "assistant": "assistant", "system": "system"},
        "conversations_key": "conversations",
        "has_system_role": True,
    }

    # Try to find role mapping from spec
    content_lower = spec_content.lower()

    # Detect ShareGPT format
    if "sharegpt" in content_lower:
        info["conversations_key"] = "conversations"
        if "human" in content_lower and "gpt" in content_lower:
            info["role_mapping"] = {"user": "human", "assistant": "gpt", "system": "system"}

    # Detect messages format
    if '"messages"' in spec_content:
        info["conversations_key"] = "messages"

    # Detect if system messages go in first user turn
    if "no system" in content_lower or "embed system" in content_lower or "no separate system" in content_lower:
        info["has_system_role"] = False

    # Look for JSONL example in code blocks
    code_blocks = re.findall(r"```(?:json|jsonl)?\n(.*?)```", spec_content, re.DOTALL)
    for block in code_blocks:
        try:
            example = json.loads(block.strip().split("\n")[0])
            if "conversations" in example:
                info["conversations_key"] = "conversations"
                if example["conversations"] and "from" in example["conversations"][0]:
                    info["role_key"] = "from"
                    info["content_key"] = "value"
                elif example["conversations"] and "role" in example["conversations"][0]:
                    info["role_key"] = "role"
                    info["content_key"] = "content"
            elif "messages" in example:
                info["conversations_key"] = "messages"
                if example["messages"] and "role" in example["messages"][0]:
                    info["role_key"] = "role"
                    info["content_key"] = "content"
            break
        except (json.JSONDecodeError, IndexError, KeyError):
            continue

    # Set defaults for role/content keys
    info.setdefault("role_key", "role")
    info.setdefault("content_key", "content")

    return info


def _format_sample(sample: dict, format_info: dict) -> dict:
    """Format a single sample according to the parsed spec."""
    conversations_key = format_info["conversations_key"]
    role_key = format_info["role_key"]
    content_key = format_info["content_key"]
    role_mapping = format_info["role_mapping"]

    if sample.get("kind") == "multi":
        # Multi-turn: accepted_response is the full conversation JSON
        try:
            messages = json.loads(sample["accepted_response"])
        except (json.JSONDecodeError, TypeError):
            messages = [
                {"role": "user", "content": sample["user_turn"]},
                {"role": "assistant", "content": sample.get("accepted_response", "")},
            ]
    else:
        # Single-turn
        messages = [
            {"role": "user", "content": sample["user_turn"]},
            {"role": "assistant", "content": sample["accepted_response"]},
        ]

    formatted_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        mapped_role = role_mapping.get(role, role)
        formatted_messages.append({
            role_key: mapped_role,
            content_key: msg.get("content", ""),
        })

    return {conversations_key: formatted_messages}
