"""Two-stage sample validation: rule checks then semantic validation."""

import re

from data_types import Sample, ValidatorOutput


async def validate(
    sample: Sample,
    validator_client: object,
    teacher_system: str,
) -> ValidatorOutput:
    """Validate a sample. Stage 1: rules (no API). Stage 2: semantic (API)."""

    # Stage 1 — Rule checks (no API call)
    if not sample.user_turn or not sample.user_turn.strip():
        return ValidatorOutput(accepted=False, reason="Empty user turn")

    if not sample.accepted_response or not sample.accepted_response.strip():
        return ValidatorOutput(accepted=False, reason="Empty assistant response")

    if len(sample.accepted_response.strip()) < 20:
        return ValidatorOutput(accepted=False, reason="Assistant response too short (< 20 chars)")

    # Check for leaked placeholder text
    placeholder_pattern = r"\{[a-zA-Z_]+\}"
    if re.search(placeholder_pattern, sample.accepted_response):
        return ValidatorOutput(accepted=False, reason="Template placeholder found in response")

    if "None" == sample.accepted_response.strip():
        return ValidatorOutput(accepted=False, reason="Response is literal 'None'")

    # Stage 2 — Semantic validation (API call)
    return await validator_client.validate(teacher_system, sample)
