"""Embedding-based deduplication of accepted samples. All local, no API calls."""

import json
import os
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


def deduplicate(input_path: str, threshold: float, model_name: str) -> int:
    """Deduplicate accepted.jsonl by user turn similarity. Returns count of removed samples."""
    if not os.path.exists(input_path):
        return 0

    with open(input_path) as f:
        lines = f.readlines()

    if len(lines) < 2:
        return 0

    samples = [json.loads(line) for line in lines]
    user_turns = [s["user_turn"] for s in samples]

    # Generate embeddings
    model = SentenceTransformer(model_name)
    embeddings = model.encode(user_turns, normalize_embeddings=True)

    # Greedy dedup: first occurrence always kept
    keep_indices: list[int] = []
    for i in range(len(embeddings)):
        is_duplicate = False
        for j in keep_indices:
            similarity = float(np.dot(embeddings[i], embeddings[j]))
            if similarity >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            keep_indices.append(i)

    removed = len(samples) - len(keep_indices)

    if removed > 0:
        # Atomic rewrite
        kept_samples = [samples[i] for i in keep_indices]
        tmp_path = input_path + ".tmp"
        with open(tmp_path, "w") as f:
            for s in kept_samples:
                f.write(json.dumps(s) + "\n")
        os.replace(tmp_path, input_path)

    return removed
