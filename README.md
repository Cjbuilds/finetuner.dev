# finetuner.dev

A synthetic SFT dataset generation pipeline that produces high-quality, model-ready training data for any open-source LLM.

Describe what your assistant should be, and finetuner.dev generates the training data to make it real — correctly formatted for Unsloth, Axolotl, or TRL. You never write a single training example by hand.

---

## How It Works

finetuner.dev orchestrates three LLM roles through five automated phases:

```
 YOU                    PIPELINE                              OUTPUT
  │                        │                                    │
  ├─ Describe project ──► Phase 1: Intake (raw capture)        │
  ├─ Answer questions ──► Phase 2: Gap Analysis + Models        │
  │                       Phase 3: Research (auto)              │
  │                       Phase 4: Generation (auto)            │
  │                       Phase 5: Report (auto)                │
  │                        │                                    │
  │                        └──────────────────────────► train.jsonl
  │                                                    eval.jsonl
```

### The Three Roles

| Role | Provider | Job |
|------|----------|-----|
| **User** | Anthropic (Claude) | Simulates realistic humans asking questions — varies persona, topic, and style |
| **Teacher** | Together AI (Qwen, DeepSeek, Llama, etc.) | Produces ideal assistant responses with optional tool use |
| **Validator** | Anthropic (Claude) | Scores responses 1-10 and rejects samples that fail quality criteria |

### The Five Phases

**Phase 1 — Raw Intake.** You describe your project in plain language. What is the assistant? Who uses it? How should it behave? Saved verbatim.

**Phase 2 — Gap Analysis.** Claude analyzes your description, identifies missing information, and asks up to 10 targeted follow-up questions — including which models to use for each role and which model you're fine-tuning. Your answers + model selections are saved. `configs/models.yaml` is written.

**Phase 3 — Research.** Fully automated. Two parallel research tasks using Claude with web search: (1) domain research — real user questions, expert vocabulary, edge cases, refusal topics; (2) finetune format research — the target model's exact chat template, special tokens, and JSONL structure from official docs and HuggingFace. A builder synthesizes findings into project identity, personas, topics, boundaries, and the finetune spec.

**Phase 4 — Generation.** The core pipeline. For each sample:
1. User client generates a realistic question (random persona + topic)
2. Teacher client generates **5 candidate responses** (rejection sampling)
3. Validator scores each candidate 1-10
4. Top 2 candidates above the score threshold are kept
5. Kept candidates pass rule validation (no empty turns, no leaked placeholders, no "None")
6. Accepted samples are semantically validated by the validator
7. After all batches: embedding-based deduplication removes near-duplicates
8. Export formats samples per the researched finetune spec → `train.jsonl` + `eval.jsonl`

**Phase 5 — Report.** Generates `outputs/report.md` with run stats, acceptance rate, score distribution, cost breakdown, and final dataset paths.

---

## Quick Start

### Prerequisites

- Python 3.11+
- API keys for [Anthropic](https://console.anthropic.com/), [Together AI](https://api.together.xyz/), and [Brave Search](https://brave.com/search/api/)

### Setup

```bash
git clone https://github.com/Cjbuilds/finetuner.dev.git
cd finetuner.dev

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys:
#   ANTHROPIC_API_KEY=sk-ant-...
#   TOGETHER_API_KEY=...
#   SEARCH_API_KEY=...
```

### Run

```bash
python run.py
```

That's it. The pipeline walks you through intake (phases 1-2), then runs research, generation, validation, dedup, and export automatically.

### Resume After Crash

The pipeline checkpoints after every batch. If it crashes or you hit Ctrl+C:

```bash
python run.py  # Automatically resumes from last checkpoint
```

### Skip Completed Phases

```bash
python run.py --from-phase 4  # Skip to generation (phases 1-3 must be complete)
```

---

## Configuration

### `configs/dataset.yaml` — Generation Parameters

```yaml
num_samples: 100           # Total samples to generate
single_ratio: 0.7          # 70% single-turn conversations
multi_ratio: 0.3           # 30% multi-turn conversations
max_turns: 4               # Max turns per multi-turn conversation
eval_split: 0.1            # 10% held out for evaluation
batch_size: 5              # Samples per batch
candidates_per_question: 5 # Rejection sampling candidates
keep_per_question: 2       # Max candidates to keep per question
min_score: 7.0             # Minimum validator score (1-10) to keep
dedup_threshold: 0.85      # Cosine similarity threshold for dedup
max_retries: 3             # API retry attempts with exponential backoff
shuffle_seed: 42           # Reproducible shuffle for train/eval split
```

### `configs/tools.yaml` — Teacher Tool Access

```yaml
use_calculator: true          # Teacher can evaluate math expressions
use_web_search: true          # Teacher can search the web
max_tool_calls_per_sample: 3  # Max tool calls per response
```

### `configs/models.yaml` — Generated at Runtime

Written during Phase 2 based on your answers. Example:

```yaml
user_model:
  name: claude-haiku-4-5-20251001
  temperature: 0.9
  max_tokens: 1024

teacher_model:
  name: Qwen/Qwen3-235B-A22B
  temperature: 0.7
  max_tokens: 4096
  thinking_tokens: disabled  # disabled | strip

validator_model:
  name: claude-sonnet-4-20250514
  temperature: 0.1
  max_tokens: 512

finetune_target:
  name: Qwen/Qwen3-30B-A3B

dedup_model: all-MiniLM-L6-v2
```

---

## Project Structure

```
finetuner.dev/
├── run.py                          # Entry point — orchestrates all phases
├── data_types.py                   # All Pydantic models
│
├── configs/
│   ├── paths.yaml                  # All file paths (no hardcoded paths in .py)
│   ├── dataset.yaml                # Generation parameters
│   ├── tools.yaml                  # Tool enablement flags
│   └── models.yaml                 # RUNTIME — model names and settings
│
├── prompts/
│   ├── render.py                   # Template rendering + caching
│   ├── user/system.md              # User simulator identity
│   ├── user/task.md                # Per-call user task template
│   ├── teacher/system.md           # Teacher identity (project-aware)
│   ├── validator/system.md         # Quality criteria + scoring rubric
│   ├── validator/task.md           # Binary validation template
│   ├── validator/score_task.md     # Numeric scoring template
│   ├── intake/gap_analysis.md      # Gap analysis instructions
│   ├── intake/questions.md         # Question generation instructions
│   ├── research/domain_research.md # Domain research instructions
│   ├── research/finetune_research.md # Format research instructions
│   └── research/builder.md         # Synthesis instructions
│
├── clients/
│   ├── user.py                     # AsyncAnthropic — user turn generation
│   ├── teacher.py                  # AsyncOpenAI (Together AI) — responses + tool use
│   └── validator.py                # AsyncAnthropic — validation + scoring
│
├── intake/
│   ├── collect.py                  # Phase 1 — freeform project description
│   └── gaps.py                     # Phase 2 — gap analysis + model selection
│
├── research/
│   ├── researcher.py               # Phase 3a — domain + finetune format research
│   └── builder.py                  # Phase 3b — synthesize into project files
│
├── pipeline/
│   ├── single_turn.py              # Single-turn generation with rejection sampling
│   ├── multi_turn.py               # Multi-turn generation with per-turn sampling
│   ├── validate_sample.py          # Two-stage validation (rules + semantic)
│   ├── dedup.py                    # Embedding-based deduplication
│   ├── export_dataset.py           # Format-agnostic export from finetune spec
│   ├── checkpoint.py               # Crash-safe progress tracking
│   └── report.py                   # Phase 5 — run report generation
│
├── tools/
│   ├── calculator.py               # Safe AST-based math evaluator
│   └── web_search.py               # Brave Search API client
│
├── dashboard/
│   └── dashboard.py                # PipelineState + Rich Live dashboard
│
├── logs/
│   └── errors.jsonl                # RUNTIME — structured error log
│
├── data/                           # RUNTIME — all generated data
│   ├── candidates/                 # All rejection sampling candidates
│   ├── raw/                        # Unvalidated samples
│   ├── clean/accepted.jsonl        # Validated + accepted samples
│   └── final/
│       ├── train.jsonl             # Final training set
│       └── eval.jsonl              # Final evaluation set
│
└── outputs/                        # RUNTIME — reports and metadata
    ├── report.md                   # Human-readable run report
    ├── stats.json                  # Sample counts and distributions
    ├── cost.json                   # Token usage and USD cost
    └── checkpoint.json             # Phase completion + sample counts
```

---

## Dashboard

A live Rich terminal dashboard shows real-time pipeline progress:

```
┌────────────────── finetuner.dev ──────────────────────────┐
│  Run: 20260310_143022  |  Elapsed: 00:12:34  |  ETA: 00:08:11  │
├── Phases ──┬────── Generation Progress ──┬── Rejection ──┤
│ ✓ Intake   │ Single: [████████░░] 52/70  │ Batch: 11/20  │
│ ✓ Gap      │ Multi:  [████░░░░░░] 14/30  │ Avg: 7.8      │
│ ✓ Research │ Total:  [██████░░░░] 66/100 │ 9-10: ██ 18   │
│ ● Generate │ Accepted: 66  Rejected: 22  │ 7-8:  ████ 31 │
│ ○ Report   │ Errors: 3                   │ 5-6:  ██ 12   │
│            │                             │ <5:   █ 5     │
├────────────┴───────── Cost ──────────────┴───────────────┤
│ User: 124,000  Teacher: 892,000  Validator: 445,000      │
│ Total: $1.2340                   8.2 samples/min         │
├───────────────── Recent Activity ────────────────────────┤
│ ✓ 14:42:31 [single] a3f2b1c8 score=8.5                  │
│ ✗ 14:42:28 [single] 7e1d4a92 Tone inconsistent with...  │
│ ✓ 14:42:25 [multi]  bc8f3e11 4 turns                    │
└──────────────────────────────────────────────────────────┘
```

---

## Rejection Sampling

Every question gets 5 candidate responses from the teacher model. The validator scores each 1-10. Only the top 2 scoring above `min_score` (default 7.0) proceed to validation. This ensures the final dataset contains only high-quality responses — not just the first thing the teacher generates.

For multi-turn conversations, rejection sampling happens **per turn** — each turn gets 5 candidates, the best is kept, and the conversation continues from there.

---

## Format-Agnostic Export

finetuner.dev has **zero hardcoded format knowledge**. It doesn't know what ChatML, ShareGPT, or Alpaca look like. During Phase 3, the research module searches official documentation for the target model's exact chat template, special tokens, and expected JSONL structure. This is written to `research/finetune_spec.md`. At export time, `export_dataset.py` parses that spec and formats accordingly.

This means finetuner.dev works with any model that has documented fine-tuning requirements — Qwen, Llama, Gemma, Mistral, DeepSeek, or anything else.

---

## Architecture Decisions

- **Intake uses Anthropic directly**, not through `clients/user.py` — the 3 clients serve only the pipeline's User/Teacher/Validator roles during generation
- **All paths from YAML** — `configs/paths.yaml` is the single source of truth for every file path. No hardcoded paths in Python files
- **All model names from YAML** — `configs/models.yaml` is written once during intake and read by every downstream module. No hardcoded model names
- **Single mutable state** — `PipelineState` is the only shared state. Created in `run.py`, passed explicitly to every function that needs it
- **Rich is isolated** — `dashboard/dashboard.py` is the only file that imports Rich. The pipeline can be tested without a terminal
- **Atomic writes** — `checkpoint.json`, `cost.json`, and `accepted.jsonl` use write-to-tmp-then-rename to prevent corruption on crash
- **Async throughout** — every API call is async, parallel where possible (research tasks run via `asyncio.gather`)

---

## License

MIT
