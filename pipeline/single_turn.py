"""Single-turn sample generation with rejection sampling."""

import json
import os
import random
from pathlib import Path

import yaml

from configs import load_yaml, resolve_path
from data_types import Candidate, Message, Sample
from logs import log_error
from pipeline.validate_sample import validate


async def generate_batch(
    batch_size: int,
    state: object,
    user_client: object,
    teacher_client: object,
    validator_client: object,
    teacher_system: str,
    dashboard: object,
) -> list[Sample]:
    """Generate a batch of single-turn samples with rejection sampling."""
    dataset_config = load_yaml(resolve_path("dataset_config"))
    candidates_per_q = dataset_config["candidates_per_question"]
    keep_per_q = dataset_config["keep_per_question"]
    min_score = dataset_config["min_score"]

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
    candidates_dir = resolve_path("candidates_single")
    raw_dir = resolve_path("raw_single")

    Path(accepted_path).parent.mkdir(parents=True, exist_ok=True)
    Path(candidates_dir).mkdir(parents=True, exist_ok=True)
    Path(raw_dir).mkdir(parents=True, exist_ok=True)

    accepted_samples: list[Sample] = []

    for _ in range(batch_size):
        try:
            # Select random persona and topic
            persona_file = random.choice(persona_files)
            with open(persona_file) as f:
                persona_text = f.read()
            topic = random.choice(core_topics or ["general"])

            # Generate user turn
            user_turn = await user_client.generate_user_turn(
                persona=persona_text,
                topic=topic,
                niches=niches_text,
                history=[],
            )

            # Generate candidates
            candidates: list[Candidate] = []
            for _ in range(candidates_per_q):
                messages = [Message(role="user", content=user_turn)]
                response, usage = await teacher_client.complete(messages)

                sample_for_score = Sample(
                    kind="single",
                    user_turn=user_turn,
                    accepted_response=response,
                    topic=topic,
                    persona=persona_file.stem,
                )

                # Score candidate
                score_result = await validator_client.score(sample_for_score)
                candidate = Candidate(
                    response=response,
                    score=score_result.score,
                    score_reason=score_result.reason,
                )
                candidates.append(candidate)

                # Update state tokens
                state.teacher_tokens += usage.input_tokens + usage.output_tokens
                state.total_cost_usd += usage.cost_usd

                # Update score buckets
                if score_result.score >= 9:
                    state.score_buckets["9-10"] += 1
                elif score_result.score >= 7:
                    state.score_buckets["7-8"] += 1
                elif score_result.score >= 5:
                    state.score_buckets["5-6"] += 1
                else:
                    state.score_buckets["<5"] += 1

            # Write all candidates
            sample_with_candidates = Sample(
                kind="single",
                user_turn=user_turn,
                candidates=candidates,
                topic=topic,
                persona=persona_file.stem,
            )
            candidates_file = os.path.join(candidates_dir, f"{sample_with_candidates.id}.jsonl")
            with open(candidates_file, "w") as f:
                f.write(json.dumps(sample_with_candidates.model_dump()) + "\n")

            state.batch_candidates += len(candidates)
            scores = [c.score for c in candidates]
            state.batch_avg_score = sum(scores) / len(scores) if scores else 0.0

            # Keep top candidates above min_score
            sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
            kept = [c for c in sorted_candidates if c.score >= min_score][:keep_per_q]
            state.batch_kept += len(kept)

            for candidate in kept:
                candidate.accepted = True
                sample = Sample(
                    kind="single",
                    user_turn=user_turn,
                    candidates=candidates,
                    accepted_response=candidate.response,
                    topic=topic,
                    persona=persona_file.stem,
                )

                # Rule validate
                validation = await validate(sample, validator_client, teacher_system)

                if validation.accepted:
                    # Append to accepted.jsonl
                    with open(accepted_path, "a") as f:
                        f.write(json.dumps(sample.model_dump()) + "\n")

                    # Write to raw dir
                    raw_file = os.path.join(raw_dir, f"{sample.id}.jsonl")
                    with open(raw_file, "w") as f:
                        f.write(json.dumps(sample.model_dump()) + "\n")

                    accepted_samples.append(sample)
                    state.accepted += 1
                    state.single_completed += 1
                    state.log({
                        "status": "accepted",
                        "id": sample.id,
                        "kind": "single",
                        "detail": f"score={candidate.score:.1f}",
                    })
                else:
                    state.rejected += 1
                    state.log({
                        "status": "rejected",
                        "id": sample.id,
                        "kind": "single",
                        "detail": validation.reason[:50],
                    })

            dashboard.refresh()

        except Exception as e:
            state.errors += 1
            state.log({
                "status": "error",
                "id": "",
                "kind": "single",
                "detail": str(e)[:50],
            })
            log_error({
                "module": "pipeline.single_turn",
                "error_type": type(e).__name__,
                "message": str(e),
            })
            dashboard.refresh()

    # Update cost.json
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
