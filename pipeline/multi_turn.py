"""Multi-turn conversation generation with per-turn rejection sampling."""

import json
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from configs import load_yaml, resolve_path
from data_types import Candidate, Message, Sample
from logs import log_error
from pipeline.validate_sample import validate


@dataclass
class ConversationContext:
    messages: list[Message] = field(default_factory=list)
    turn_count: int = 0


async def generate_batch(
    batch_size: int,
    state: object,
    user_client: object,
    teacher_client: object,
    validator_client: object,
    teacher_system: str,
    dashboard: object,
) -> list[Sample]:
    """Generate a batch of multi-turn conversation samples."""
    dataset_config = load_yaml(resolve_path("dataset_config"))
    candidates_per_q = dataset_config["candidates_per_question"]
    keep_per_q = dataset_config["keep_per_question"]
    min_score = dataset_config["min_score"]
    max_turns = dataset_config["max_turns"]

    # Load personas and topics
    personas_dir = resolve_path("personas_dir")
    persona_files = list(Path(personas_dir).glob("*.md"))
    topics_core_path = resolve_path("topics_core")
    topics_niches_path = resolve_path("topics_niches")

    with open(topics_core_path) as f:
        core_topics = yaml.safe_load(f)
    with open(topics_niches_path) as f:
        niches_topics = yaml.safe_load(f)

    niches_text = "\n".join(f"- {t}" for t in (niches_topics or []))
    accepted_path = resolve_path("accepted_samples")
    candidates_dir = resolve_path("candidates_multi")
    raw_dir = resolve_path("raw_multi")

    Path(accepted_path).parent.mkdir(parents=True, exist_ok=True)
    Path(candidates_dir).mkdir(parents=True, exist_ok=True)
    Path(raw_dir).mkdir(parents=True, exist_ok=True)

    accepted_samples: list[Sample] = []

    for _ in range(batch_size):
        try:
            persona_file = random.choice(persona_files)
            with open(persona_file) as f:
                persona_text = f.read()
            topic = random.choice(core_topics or ["general"])

            ctx = ConversationContext()
            conversation_failed = False

            for turn in range(max_turns):
                # Generate user turn
                history = [{"role": m.role, "content": m.content} for m in ctx.messages]
                user_turn = await user_client.generate_user_turn(
                    persona=persona_text,
                    topic=topic,
                    niches=niches_text,
                    history=history,
                )
                ctx.messages.append(Message(role="user", content=user_turn))

                # Rejection sampling for this turn
                candidates: list[Candidate] = []
                for _ in range(candidates_per_q):
                    response, usage = await teacher_client.complete(ctx.messages)

                    turn_sample = Sample(
                        kind="multi",
                        user_turn=user_turn,
                        accepted_response=response,
                        topic=topic,
                        persona=persona_file.stem,
                    )
                    score_result = await validator_client.score(turn_sample)

                    candidate = Candidate(
                        response=response,
                        score=score_result.score,
                        score_reason=score_result.reason,
                    )
                    candidates.append(candidate)

                    state.teacher_tokens += usage.input_tokens + usage.output_tokens
                    state.total_cost_usd += usage.cost_usd

                    if score_result.score >= 9:
                        state.score_buckets["9-10"] += 1
                    elif score_result.score >= 7:
                        state.score_buckets["7-8"] += 1
                    elif score_result.score >= 5:
                        state.score_buckets["5-6"] += 1
                    else:
                        state.score_buckets["<5"] += 1

                state.batch_candidates += len(candidates)
                scores = [c.score for c in candidates]
                state.batch_avg_score = sum(scores) / len(scores) if scores else 0.0

                # Keep best candidate above min_score
                sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
                best = next((c for c in sorted_candidates if c.score >= min_score), None)

                if best is None:
                    conversation_failed = True
                    state.rejected += 1
                    state.log({
                        "status": "rejected",
                        "id": "",
                        "kind": "multi",
                        "detail": f"No candidate above {min_score} at turn {turn + 1}",
                    })
                    break

                best.accepted = True
                ctx.messages.append(Message(role="assistant", content=best.response))
                ctx.turn_count += 1
                state.batch_kept += 1

            if conversation_failed:
                dashboard.refresh()
                continue

            # Full conversation complete — create sample
            full_user_turn = json.dumps(
                [{"role": m.role, "content": m.content} for m in ctx.messages],
                indent=2,
            )
            sample = Sample(
                kind="multi",
                user_turn=ctx.messages[0].content,
                candidates=[],
                accepted_response=full_user_turn,
                topic=topic,
                persona=persona_file.stem,
            )

            # Write candidates
            candidates_file = os.path.join(candidates_dir, f"{sample.id}.jsonl")
            with open(candidates_file, "w") as f:
                f.write(json.dumps(sample.model_dump()) + "\n")

            # Validate full conversation
            validation = await validate(sample, validator_client, teacher_system)

            if validation.accepted:
                with open(accepted_path, "a") as f:
                    f.write(json.dumps(sample.model_dump()) + "\n")

                raw_file = os.path.join(raw_dir, f"{sample.id}.jsonl")
                with open(raw_file, "w") as f:
                    f.write(json.dumps(sample.model_dump()) + "\n")

                accepted_samples.append(sample)
                state.accepted += 1
                state.multi_completed += 1
                state.log({
                    "status": "accepted",
                    "id": sample.id,
                    "kind": "multi",
                    "detail": f"{ctx.turn_count} turns",
                })
            else:
                state.rejected += 1
                state.log({
                    "status": "rejected",
                    "id": sample.id,
                    "kind": "multi",
                    "detail": validation.reason[:50],
                })

            dashboard.refresh()

        except Exception as e:
            state.errors += 1
            state.log({
                "status": "error",
                "id": "",
                "kind": "multi",
                "detail": str(e)[:50],
            })
            log_error({
                "module": "pipeline.multi_turn",
                "error_type": type(e).__name__,
                "message": str(e),
            })
            dashboard.refresh()

    _update_cost(state)
    return accepted_samples


def _update_cost(state: object) -> None:
    """Write current cost state to cost.json."""
    cost_path = resolve_path("cost")
    Path(cost_path).parent.mkdir(parents=True, exist_ok=True)
    cost_data = {
        "user_tokens": state.user_tokens,
        "teacher_tokens": state.teacher_tokens,
        "validator_tokens": state.validator_tokens,
        "total_cost_usd": state.total_cost_usd,
    }
    tmp_path = cost_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(cost_data, f, indent=2)
    os.replace(tmp_path, cost_path)
