# finetuner.dev — Complete Technical Specification

> **This document is the single source of truth for building finetuner.dev.**
> Load this into Claude Code (Opus 4.6) and build the entire project from it.
> Every file, every phase, every relationship, every constraint is documented here.
> Do not infer. Do not add. Build exactly what is described.

---

## Table of Contents

1. [What is finetuner.dev](#1-what-is-finetunerdev)
2. [Goal](#2-goal)
3. [Core Philosophy](#3-core-philosophy)
4. [Complete File Structure](#4-complete-file-structure)
5. [Architecture Overview](#5-architecture-overview)
6. [The Five Phases — Complete Workflow](#6-the-five-phases--complete-workflow)
7. [Roles: User, Teacher, Validator](#7-roles-user-teacher-validator)
8. [File-by-File Specification](#8-file-by-file-specification)
9. [Dashboard — Architecture and Patterns](#9-dashboard--architecture-and-patterns)
10. [Data Flow and File Relationships](#10-data-flow-and-file-relationships)
11. [Code Standards](#11-code-standards)

---

## 1. What is finetuner.dev

finetuner.dev is a **synthetic SFT (Supervised Fine-Tuning) dataset generation pipeline** that produces high-quality, model-ready training data for any open-source LLM.

Given a plain-language description of a project — what the assistant should be, how it should behave, who it serves — finetuner.dev runs an end-to-end pipeline that:

1. Understands your project deeply through structured intake
2. Researches the target fine-tune model's required data format from official documentation
3. Generates synthetic training conversations using frontier LLMs
4. Validates and scores every sample with a separate judge model
5. Exports a clean, correctly-formatted dataset ready for Unsloth, Axolotl, or TRL

The operator never writes a single training example by hand. The system produces them, judges them, filters them, and formats them.

---

## 2. Goal

The goal is a dataset that makes the fine-tuned model behave exactly as the operator intended — not a generic assistant, but a specific one with specific knowledge, tone, boundaries, and capabilities.

finetuner.dev achieves this by:

- Generating user turns that reflect realistic personas (expert, beginner, adversarial) asking about real topics
- Using a powerful teacher model to produce the ideal responses those users should receive
- Rejecting samples that don't meet quality standards before they enter training data
- Formatting output to exactly what the target model's fine-tuning framework expects

The final output is `data/final/train.jsonl` and `data/final/eval.jsonl`. These files are the product. Everything else is infrastructure to produce them.

---

## 3. Core Philosophy

These principles govern every implementation decision. When in doubt, return to them.

**Clean over clever.** Every file does one thing. No file imports from a file it doesn't directly depend on. No circular dependencies. No helper utilities scattered across unrelated modules.

**No dead code.** If a function isn't called, it doesn't exist. If a config key isn't read, it isn't defined. No "we might need this later" code.

**Minimal working.** The simplest implementation that actually works. No premature abstraction. A function that's called once in one place does not need to be a class.

**State flows one direction.** Intake writes configs. Research reads configs and writes project files. Pipeline reads project files and generates data. Export reads data and writes the final dataset. No phase reads outputs of a later phase. No phase writes to the inputs of an earlier phase.

**Terminal is for the dashboard only.** No `print()` anywhere in the pipeline. All terminal output goes through `dashboard/dashboard.py`. All file output goes through the appropriate writer in its phase. No exceptions.

**Configs are written once and read many times.** `configs/models.yaml` is written by intake and read by every subsequent phase. It is never written again after phase 2 completes. No phase may modify a config after it has been written.

---

## 4. Complete File Structure

```
finetuner.dev/
│
├── .env.example                        # env var names — no values
├── requirements.txt                    # all Python dependencies
├── run.py                              # entry point — enforces phase order
├── types.py                            # all Pydantic models for the project
│
├── configs/                            # operational configuration — never hardcoded in code
│   ├── models.yaml                     # WRITTEN by intake phase 2 — model names, temps, limits
│   ├── dataset.yaml                    # static — sample counts, ratios, batch size, dedup threshold
│   ├── tools.yaml                      # static — which tools are enabled and limits
│   └── paths.yaml                      # static — all file paths in one place
│
├── intake/                             # phase 1 + 2 — understand the project
│   ├── collect.py                      # phase 1 — freeform project description CLI
│   ├── gaps.py                         # phase 2 — gap analysis, model selection, writes models.yaml
│   ├── raw_intake.md                   # RUNTIME GENERATED — your phase 1 answers
│   └── enriched_intake.md              # RUNTIME GENERATED — your phase 2 answers
│
├── research/                           # phase 3 — automated research
│   ├── researcher.py                   # Opus + web search — domain + fine-tune format research
│   ├── builder.py                      # synthesises research findings into project/ files
│   ├── finetune_spec.md                # RUNTIME GENERATED — target model format, tokens, structure
│   └── research_notes.md              # RUNTIME GENERATED — raw research findings
│
├── project/                            # OUTPUT of research — never manually edited
│   ├── identity.md                     # what the assistant is and how it behaves
│   ├── use_cases.md                    # what users will use it for
│   ├── boundaries.md                   # what it will and will not do
│   ├── personas/
│   │   ├── expert.md                   # expert user persona profile
│   │   ├── beginner.md                 # beginner user persona profile
│   │   └── adversarial.md             # adversarial user persona profile
│   └── topics/
│       ├── core.yaml                   # primary topics the assistant covers
│       └── niches.yaml                 # secondary / edge-case topics
│
├── clients/                            # API clients — one per role
│   ├── user.py                         # Anthropic async client — generates user turns
│   ├── teacher.py                      # Together AI async client (OpenAI-compatible) — generates responses
│   └── validator.py                    # Anthropic async client — validates and scores samples
│
├── prompts/                            # all prompt templates — Markdown with {placeholders}
│   ├── render.py                       # render(template, **kwargs) — single rendering seam
│   ├── user/
│   │   ├── system.md                   # permanent user simulator identity
│   │   └── task.md                     # {persona}, {topic}, {niches}, {history} placeholders
│   ├── teacher/
│   │   └── system.md                   # {project_identity} placeholder — no task.md
│   ├── validator/
│   │   ├── system.md                   # judging rules and scoring criteria
│   │   ├── task.md                     # {teacher_system}, {sample} — for binary validation
│   │   └── score_task.md               # {sample} — for 1-10 scoring in rejection sampling
│   ├── intake/
│   │   ├── gap_analysis.md             # instructs Opus to find what's missing in raw intake
│   │   └── questions.md                # instructs Opus to generate targeted questions
│   └── research/
│       ├── domain_research.md          # guides Opus web search on domain, personas, topics
│       ├── finetune_research.md        # guides Opus web search on target model fine-tune format
│       └── builder.md                  # guides Opus to synthesise findings into project/ files
│
├── tools/                              # real tools available to teacher model
│   ├── calculator.py                   # safe AST-based expression evaluator — no exec()
│   └── web_search.py                   # Brave Search API via httpx
│
├── pipeline/                           # phase 4 — sample generation and validation
│   ├── single_turn.py                  # generates single-turn samples
│   ├── multi_turn.py                   # generates multi-turn conversation samples
│   ├── validate_sample.py              # rule checks then Sonnet semantic validation
│   ├── dedup.py                        # local embedding similarity deduplication
│   ├── export_dataset.py               # reads finetune_spec.md, formats and writes final files
│   ├── checkpoint.py                   # crash-safe progress tracking
│   └── report.py                       # phase 5 — generates outputs/report.md
│
├── dashboard/
│   └── dashboard.py                    # PipelineState dataclass + Dashboard renderer (Rich)
│
├── data/
│   ├── raw/
│   │   ├── single/                     # unvalidated single-turn samples (.jsonl per batch)
│   │   └── multi/                      # unvalidated multi-turn samples (.jsonl per batch)
│   ├── candidates/
│   │   ├── single/                     # rejection sampling candidates (5 per question)
│   │   └── multi/                      # rejection sampling candidates (5 per question)
│   ├── clean/
│   │   └── accepted.jsonl              # all validated samples regardless of single/multi origin
│   └── final/
│       ├── train.jsonl                 # final training set
│       └── eval.jsonl                  # final evaluation set
│
├── logs/
│   ├── run_YYYYMMDD_HHMMSS.jsonl       # per-run structured event log
│   └── errors.jsonl                    # all errors across all runs appended
│
└── outputs/
    ├── report.md                       # RUNTIME GENERATED — full run report (phase 5)
    ├── stats.json                      # sample counts, acceptance rate, score distribution
    ├── cost.json                       # token usage and USD cost per role — written per batch
    └── checkpoint.json                 # phase completion + sample counts — crash recovery
```

---

## 5. Architecture Overview

finetuner.dev has five distinct layers that execute in sequence. Each layer has one job. No layer does two jobs.

### Layer 1 — Intake (Phases 1 & 2)
Human-in-the-loop. The operator describes their project in plain language. Opus analyzes the description, finds gaps, asks targeted questions including model selection, and writes `configs/models.yaml`. Nothing automated runs until intake is complete.

### Layer 2 — Research (Phase 3)
Fully automated. Opus with web search reads the enriched intake and performs two research tasks in parallel: domain research (what the assistant knows, who it serves, how it behaves) and fine-tune format research (what format the target model requires, what special tokens it uses, what frameworks support it). Builder synthesises all findings into `project/` files and `research/finetune_spec.md`.

### Layer 3 — Generation (Phase 4, Part 1)
The pipeline generates training samples. User client simulates realistic user turns. Teacher client produces ideal responses. For each question, 5 candidate responses are generated (rejection sampling). All candidates are stored in `data/candidates/`.

### Layer 4 — Validation (Phase 4, Part 2)
Each candidate is scored 1-10 by the validator. The top 2 per question are kept if they score above the threshold defined in `dataset.yaml`. Kept samples move to `data/clean/accepted.jsonl`. Below-threshold samples are discarded. After all samples are collected, deduplication runs against the full accepted set.

### Layer 5 — Export and Report (Phases 4-5)
`export_dataset.py` reads `research/finetune_spec.md` to determine the exact output format for the target model. It shuffles accepted samples, applies the train/eval split from `dataset.yaml`, and writes `data/final/train.jsonl` and `data/final/eval.jsonl`. `report.py` then generates `outputs/report.md`.

### State Object
A single `PipelineState` dataclass in `dashboard/dashboard.py` is the only shared mutable state in the system. Every pipeline component receives a reference to it and writes to it. The dashboard reads from it and renders. This is the only place where state crosses module boundaries.

---

## 6. The Five Phases — Complete Workflow

### Phase 1 — Intake: Raw Collection

**File:** `intake/collect.py`
**Operator action required:** Yes — you type your project description
**Produces:** `intake/raw_intake.md`
**Requires:** Nothing

`collect.py` opens an interactive CLI session. It prompts the operator with a single open question: describe your project. The operator types a freeform description — what the assistant is, what it does, who uses it, what model they want to fine-tune, anything relevant.

The input is saved verbatim to `intake/raw_intake.md`. No Opus call happens in this phase. No analysis. No questions. Just capture.

`collect.py` writes `outputs/checkpoint.json` with `phase_1_complete: true` before exiting.

**Why this phase exists:** The pipeline needs raw material from the operator's own words before it can ask intelligent follow-up questions. Asking questions with no prior context produces generic questions. Asking questions after reading a description produces targeted ones.

---

### Phase 2 — Intake: Gap Analysis and Model Selection

**File:** `intake/gaps.py`
**Operator action required:** Yes — you answer up to 10 targeted questions
**Produces:** `intake/enriched_intake.md`, `configs/models.yaml`
**Requires:** `intake/raw_intake.md`

`gaps.py` reads `raw_intake.md` and makes two sequential Opus calls.

**Call 1 — Gap Analysis:**
Uses `prompts/intake/gap_analysis.md` as system prompt with `raw_intake.md` content injected. Opus identifies what critical information is missing or ambiguous. Output is an internal analysis — not shown to the operator.

**Call 2 — Question Generation:**
Uses `prompts/intake/questions.md` as system prompt with the gap analysis injected. Opus generates a maximum of 10 questions. The prompt explicitly instructs that the following four model-selection questions must always be included regardless of what other gaps exist:

1. What model should generate user turns (the question asker)?
2. What model should act as teacher (the ideal response generator)?
3. What model should validate and score responses?
4. What model are you fine-tuning? (This determines the data format of the final dataset.)

The 10-question maximum includes these four. The remaining 6 slots are for domain-specific gaps.

The questions are presented to the operator one at a time in the CLI. Answers are collected and saved to `intake/enriched_intake.md`.

After all answers are collected, `gaps.py` parses the model selection answers and writes `configs/models.yaml` with the following structure:

```yaml
user_model:
  name: <answer from question 1>
  temperature: 0.9
  max_tokens: 1024

teacher_model:
  name: <answer from question 2>
  temperature: 0.7
  max_tokens: 4096
  thinking_tokens: disabled   # disabled | strip

validator_model:
  name: <answer from question 3>
  temperature: 0.1
  max_tokens: 512

finetune_target:
  name: <answer from question 4>

dedup_model: all-MiniLM-L6-v2
```

`configs/models.yaml` is written exactly once. It is never modified again. If `models.yaml` already exists and is complete, `gaps.py` skips writing it.

`gaps.py` writes `phase_2_complete: true` to checkpoint before exiting.

**Why this phase exists:** The operator cannot be expected to know every detail the pipeline needs. Structured gap analysis produces targeted questions. Model selection must happen here because every downstream phase depends on knowing which models to call and which format to produce.

---

### Phase 3 — Research

**Files:** `research/researcher.py`, `research/builder.py`
**Operator action required:** No — fully automated
**Produces:** `project/` (all files), `research/finetune_spec.md`, `research/research_notes.md`
**Requires:** `intake/enriched_intake.md`, `configs/models.yaml`
**Model used:** Opus 4.6 with web search enabled (deep research mode)

This is the most computationally expensive phase. It runs four research tasks then synthesises them.

**Task 1 — Domain Research:**
`researcher.py` uses `prompts/research/domain_research.md` as system prompt with `enriched_intake.md` injected. Opus performs web searches to understand: the domain the assistant operates in, common user personas, real questions users ask, edge cases and adversarial inputs, tone and vocabulary expectations, topics the assistant must cover deeply, topics the assistant should refuse or redirect.

**Task 2 — Fine-Tune Format Research:**
`researcher.py` reads `finetune_target.name` from `configs/models.yaml`. It uses `prompts/research/finetune_research.md` as system prompt with the model name injected. Opus performs web searches against official documentation, Hugging Face model cards, Unsloth docs, Axolotl docs, and TRL docs to find: the required chat template, special tokens (BOS, EOS, IM_START, IM_END, etc.), recommended data format (ChatML, ShareGPT, Alpaca, or custom), recommended context length for SFT, any framework-specific requirements or known quirks.

All raw findings from both tasks are appended to `research/research_notes.md`.

**Synthesis — builder.py:**
`builder.py` reads `research_notes.md` and `enriched_intake.md`. It uses `prompts/research/builder.md` as system prompt. It makes one Opus call per output file and writes each `project/` file and `research/finetune_spec.md`.

`research/finetune_spec.md` must contain:
- The exact chat template string for the target model
- All special tokens and their exact string values
- The expected JSONL structure for each training example
- Whether the model uses a `system` field or embeds system in the first human turn
- The recommended max sequence length
- Any Unsloth-specific flags or configurations

`research/finetune_spec.md` is the contract between the research phase and the export phase. `export_dataset.py` reads nothing from research except this file.

`researcher.py` and `builder.py` write `phase_3_complete: true` to checkpoint before exiting.

**Why this phase exists:** Hard-coding ChatML into export is wrong. Different models use different formats. The fine-tune spec must be researched per target model, per run. The project identity must be researched from real domain knowledge, not invented.

---

### Phase 4 — Generation, Validation, Deduplication, Export

**Files:** `pipeline/single_turn.py`, `pipeline/multi_turn.py`, `pipeline/validate_sample.py`, `pipeline/dedup.py`, `pipeline/export_dataset.py`, `pipeline/checkpoint.py`
**Operator action required:** No — fully automated
**Produces:** `data/final/train.jsonl`, `data/final/eval.jsonl`, `outputs/stats.json`, `outputs/cost.json`
**Requires:** All `project/` files, `research/finetune_spec.md`, `configs/models.yaml`, `configs/dataset.yaml`

This is the core of the pipeline. It runs in the following sequence:

#### 4a — Batch Generation (Rejection Sampling)

`main.py` reads `dataset.yaml` for `num_samples`, `single_ratio`, `multi_ratio`, and `batch_size`. It computes `single_target` and `multi_target`.

For each batch:

1. User client generates a user turn using a randomly selected persona from `project/personas/` and a randomly selected topic from `project/topics/core.yaml` or `project/topics/niches.yaml`
2. For that user turn, teacher client generates **5 candidate responses** (rejection sampling)
3. All 5 candidates are written to `data/candidates/single/` or `data/candidates/multi/` as a single JSONL entry with all candidates embedded
4. Validator scores each candidate 1-10 using `prompts/validator/score_task.md`
5. The top 2 candidates that score above the threshold in `dataset.yaml` (`min_score`) are kept
6. Kept candidates pass through rule validation in `validate_sample.py` (schema checks, length checks, no empty turns)
7. Samples that pass rules move to `data/raw/single/` or `data/raw/multi/`
8. Accepted samples are appended to `data/clean/accepted.jsonl`
9. Token usage and cost are calculated and appended to `outputs/cost.json` after every batch
10. `checkpoint.py` updates `single_completed` and `multi_completed` counters

The pipeline alternates between single and multi-turn batches to maintain the configured ratio.

For **multi-turn**, `multi_turn.py` maintains a `ConversationContext` per conversation — a list of prior message pairs. After each turn pair is generated and the conversation reaches the configured `max_turns`, the entire conversation is serialised as one multi-turn sample. `ConversationContext` is a simple dataclass defined inside `multi_turn.py`. It is not a separate file.

#### 4b — Deduplication

After all batches complete, `dedup.py` runs against `data/clean/accepted.jsonl`. It uses `sentence-transformers` with the model specified in `configs/models.yaml` under `dedup_model` to generate local embeddings of all user turns. Cosine similarity is computed pairwise. Any sample with similarity above `dedup_threshold` in `dataset.yaml` to an already-kept sample is discarded. Greedy algorithm — first occurrence is always kept.

Dedup runs entirely locally. No API calls. No cost.

#### 4c — Export

`export_dataset.py` reads `research/finetune_spec.md` and parses the required format. It reads all remaining samples from `data/clean/accepted.jsonl`. It:

1. Shuffles all samples (seeded for reproducibility — seed in `dataset.yaml`)
2. Applies the train/eval split ratio from `dataset.yaml`
3. Formats each sample according to `finetune_spec.md`
4. Writes `data/final/train.jsonl` and `data/final/eval.jsonl`
5. Writes `outputs/stats.json` with final counts

`export_dataset.py` has no knowledge of ChatML, ShareGPT, or any specific format. It only knows how to read `finetune_spec.md` and apply the template it finds there. The format is entirely determined by research.

---

### Phase 5 — Report

**File:** `pipeline/report.py`
**Operator action required:** No
**Produces:** `outputs/report.md`
**Requires:** `outputs/stats.json`, `outputs/cost.json`, `data/final/train.jsonl`, `data/final/eval.jsonl`

`report.py` reads all output files and generates a human-readable Markdown report covering: run ID, elapsed time, samples generated vs. targets, acceptance rate, score distribution, dedup removals, cost breakdown per role, final dataset size, and the path to the final files.

This is the last file written. Its existence indicates a complete successful run.

---

## 7. Roles: User, Teacher, Validator

The three LLM roles are the heart of the system. Each has a distinct job, a distinct client, a distinct set of prompts. They never share a client. They never share a prompt file.

### The User Role

**Client:** `clients/user.py`
**API:** Anthropic (AsyncAnthropic)
**Prompt files:** `prompts/user/system.md`, `prompts/user/task.md`

The user role simulates realistic humans asking questions. It is not a helpful assistant. It is a question generator.

`user/system.md` establishes a permanent identity: a question simulator that produces realistic, varied user turns based on personas and topics. This system prompt never changes between calls.

`user/task.md` is rendered fresh for each call with:
- `{persona}` — the full text of one persona file from `project/personas/`
- `{topic}` — one topic selected from `project/topics/`
- `{niches}` — the niche topics list from `project/topics/niches.yaml`
- `{history}` — the prior conversation turns (for multi-turn only; empty for single-turn)

The user client's output is a single user message string. Nothing else. It does not produce the assistant response. It produces only the question.

**In scope:** Generating realistic user turns. Varying style by persona. Following topic constraints.
**Out of scope:** Generating responses. Evaluating anything. Calling tools. Knowing what the assistant is.

---

### The Teacher Role

**Client:** `clients/teacher.py`
**API:** Together AI via OpenAI-compatible endpoint (`https://api.together.xyz/v1`)
**Prompt files:** `prompts/teacher/system.md`

The teacher role produces the ideal responses that the fine-tuned model should learn to replicate.

`teacher/system.md` has a single `{project_identity}` placeholder. At pipeline initialisation, `render.py` renders the system prompt by reading `project/identity.md`, `project/use_cases.md`, and `project/boundaries.md` and injecting them as `project_identity`. This rendering happens once at init and is cached — not per-call.

The teacher receives the conversation history directly as API message history in OpenAI format. There is no `task.md` for the teacher because the conversation itself is the input — no additional template is needed.

The teacher may use tools. If `tools.yaml` has `use_calculator: true`, the calculator tool definition is passed in the API call. If `use_web_search: true`, the web search tool definition is passed. Tool results are resolved inside `teacher.py` and the final response (after tool use) is what gets stored.

The teacher client generates responses in a loop of **5 candidates per question** for rejection sampling. All 5 use the same system prompt and the same user turn. Temperature is set in `configs/models.yaml` under `teacher_model.temperature`.

If `thinking_tokens: disabled`, the Together AI call includes `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`. If `thinking_tokens: strip`, the call allows thinking but strips `<think>...</think>` tags from the final stored response.

**In scope:** Producing ideal assistant responses. Using tools when needed. Generating 5 candidates per question.
**Out of scope:** Generating user turns. Evaluating quality. Knowing anything about the pipeline.

---

### The Validator Role

**Client:** `clients/validator.py`
**API:** Anthropic (AsyncAnthropic)
**Prompt files:** `prompts/validator/system.md`, `prompts/validator/task.md`, `prompts/validator/score_task.md`

The validator has two modes: **validate** and **score**. These are separate methods on the validator client.

**Validate mode** (`validate_sample.py` calls this):
Used for binary pass/fail on rule checks. Stage 1 is code-only — check that the sample has a non-empty user turn, a non-empty assistant turn, the assistant turn is above a minimum length, no placeholder text leaked from templates. If any rule fails, the sample is rejected immediately with no Anthropic API call made. Stage 2 is semantic — only if stage 1 passes. Uses `prompts/validator/task.md` with `{teacher_system}` (the rendered teacher system prompt) and `{sample}` (the full conversation JSON) injected. Validator returns a binary `accepted: true/false` with a reason string.

**Score mode** (`pipeline/single_turn.py` and `multi_turn.py` call this after teacher generates 5 candidates):
Uses `prompts/validator/score_task.md`. Validator returns a score from 1-10 with a reason. Score is stored alongside the candidate in `data/candidates/`. The top 2 candidates above `min_score` from `dataset.yaml` proceed to validate mode.

The validator uses a different model family than the teacher. This is intentional. A Qwen model grading Qwen outputs would be biased toward its own style. Using an Anthropic model as validator catches quality issues the teacher would miss.

`validator/system.md` defines what good looks like: accuracy, helpfulness, tone consistency with the project identity, appropriate use of tools, appropriate length, no hallucination, no contradiction with `project/boundaries.md`.

**In scope:** Binary validation. Numeric scoring. Reasoning about quality.
**Out of scope:** Generating any content. Modifying samples. Knowing anything about the pipeline.

---

## 8. File-by-File Specification

### `run.py`

Entry point. Reads `outputs/checkpoint.json` to determine which phases are complete. Enforces phase ordering — phase N cannot start until phase N-1 is marked complete in checkpoint. Supports `--from-phase N` CLI flag to restart from a specific phase (only valid if all prior phases are complete). Passes shared `PipelineState` to `Dashboard` and starts it before any phase begins. Calls each phase module in sequence. Writes final checkpoint on completion.

**In scope:** Phase orchestration, checkpoint enforcement, dashboard lifecycle.
**Out of scope:** Any pipeline logic, any prompt rendering, any API calls.

---

### `types.py`

All Pydantic models for the project. Every data structure that crosses a module boundary is defined here. No Pydantic model is defined anywhere else.

Models to define:
- `Message` — role (user/assistant/system), content string
- `ToolCall` — tool name, arguments dict
- `ToolResult` — tool name, result string, is_error bool
- `Candidate` — teacher response string, score float, score_reason string, accepted bool
- `Sample` — id (uuid), kind (single/multi), user_turn string, candidates list, accepted_response string, topic string, persona string
- `TokenUsage` — role string, input_tokens int, output_tokens int, cost_usd float
- `ValidatorOutput` — accepted bool, reason string
- `ScoreOutput` — score float, reason string
- `CheckpointState` — phase completion bools, single_completed int, multi_completed int

**In scope:** Data models only. No logic. No methods beyond Pydantic validators.
**Out of scope:** Any computation, any I/O, any imports except Pydantic and Python stdlib.

---

### `configs/models.yaml`

Written by `intake/gaps.py`. Read by `clients/user.py`, `clients/teacher.py`, `clients/validator.py`, `pipeline/dedup.py`. Never written again after phase 2.

Structure is defined in Phase 2 documentation above. Every downstream module that needs a model name reads it from here.

**In scope:** Model names, temperatures, token limits, thinking token setting, dedup model name.
**Out of scope:** Anything about the dataset structure, paths, or tools.

---

### `configs/dataset.yaml`

Static. Written by the operator before any run. Contains: `num_samples`, `single_ratio`, `multi_ratio`, `max_turns` (for multi-turn), `eval_split`, `batch_size`, `candidates_per_question` (always 5), `keep_per_question` (always 2), `min_score` (threshold for keeping a candidate), `dedup_threshold`, `max_retries`, `shuffle_seed`.

**In scope:** Dataset shape and generation parameters.
**Out of scope:** Model names, paths, tool settings.

---

### `configs/tools.yaml`

Static. Contains: `use_calculator` (bool), `use_web_search` (bool), `max_tool_calls_per_sample` (int). Read by `clients/teacher.py` to configure which tool definitions to pass in API calls.

**In scope:** Tool enablement flags and limits.
**Out of scope:** Tool implementations, model settings, dataset settings.

---

### `configs/paths.yaml`

Static. Contains all file paths used across the project as named keys. Every module that reads or writes a file gets the path from here — no hardcoded paths anywhere in the codebase. Example: `accepted_samples: data/clean/accepted.jsonl`, `finetune_spec: research/finetune_spec.md`.

**In scope:** File path definitions.
**Out of scope:** Everything else.

---

### `intake/collect.py`

Runs phase 1. Opens CLI. Presents a prompt. Reads operator input (supports multiline — ends on empty line or sentinel). Writes verbatim to `intake/raw_intake.md`. Updates checkpoint. Exits.

No Opus call. No analysis. No validation of input.

**In scope:** CLI input capture, file write, checkpoint update.
**Out of scope:** Any LLM call, any analysis, any question generation.

---

### `intake/gaps.py`

Runs phase 2. Reads `intake/raw_intake.md`. Makes two sequential Opus calls (gap analysis, question generation). Presents questions to operator one at a time. Collects answers. Writes `intake/enriched_intake.md`. Parses model selection answers. Writes `configs/models.yaml`. Updates checkpoint.

The gap analysis call is internal — its output is injected into the question generation call, never shown to the operator.

The four model-selection questions are always generated. They may be the first four questions or interleaved — the prompt specifies their placement.

**In scope:** Gap analysis, question generation, CLI Q&A, models.yaml generation.
**Out of scope:** Domain research, file synthesis, any generation pipeline logic.

---

### `research/researcher.py`

Runs phase 3 part 1. Makes two Opus + web search calls: domain research and fine-tune format research. Both use their respective prompt files. Raw findings from both are written to `research/research_notes.md`. Calls `builder.py` to synthesise. Updates checkpoint.

Web search is enabled by passing the web search tool definition in the Opus API call — same pattern as the Anthropic API tool use. Opus decides when and what to search.

**In scope:** Domain research, fine-tune format research, writing research_notes.md.
**Out of scope:** Synthesising into project files (that's builder.py), any generation logic.

---

### `research/builder.py`

Reads `research/research_notes.md` and `intake/enriched_intake.md`. Makes one Opus call per output file using `prompts/research/builder.md`. Writes all `project/` files and `research/finetune_spec.md`. Does not do any web searching.

Order of writes matters: `identity.md` first (other files may reference it), then `use_cases.md`, `boundaries.md`, personas, topics, `finetune_spec.md` last.

**In scope:** Synthesising research into structured project files.
**Out of scope:** Any research (web search), any pipeline logic.

---

### `clients/user.py`

Wraps `AsyncAnthropic`. Exposes one async method: `generate_user_turn(persona: str, topic: str, niches: str, history: list[Message]) -> str`. Reads model config from `configs/models.yaml`. Renders `prompts/user/task.md` with the given parameters using `prompts/render.py`. Sends the call. Returns the content string.

System prompt is cached on client init via `render.py`'s cached system loader.

**In scope:** User turn generation only.
**Out of scope:** Response generation, validation, tool use.

---

### `clients/teacher.py`

Wraps `AsyncOpenAI` pointed at `https://api.together.xyz/v1`. Exposes one async method: `complete(messages: list[Message]) -> tuple[str, TokenUsage]`. Reads model config from `configs/models.yaml` and tool config from `configs/tools.yaml`. Passes tool definitions if enabled. Handles tool call resolution inline (calls the actual tool, appends result, makes follow-up call). Strips thinking tags if `thinking_tokens: strip`. Returns final response string and token usage.

System prompt is cached on client init.

**In scope:** Teacher response generation, tool call resolution, thinking token handling.
**Out of scope:** User turn generation, validation, scoring.

---

### `clients/validator.py`

Wraps `AsyncAnthropic`. Exposes two async methods: `validate(teacher_system: str, sample: Sample) -> ValidatorOutput` and `score(sample: Sample) -> ScoreOutput`. Reads model config from `configs/models.yaml`. Uses different prompt templates for each method. Returns structured Pydantic objects.

**In scope:** Binary validation, numeric scoring.
**Out of scope:** Content generation, tool use, pipeline logic.

---

### `prompts/render.py`

Two functions only:

`render(template_path: str, **kwargs) -> str` — reads the template file, calls `.format(**kwargs)`, raises a clear `KeyError` with the placeholder name if a key is missing. No silent failures.

`render_system(role: str) -> str` — reads `prompts/{role}/system.md`, renders it with no kwargs (system prompts have no runtime placeholders except teacher's `{project_identity}` which is injected once at init). Caches the result. Subsequent calls for the same role return cached string without re-reading file.

No other functions. No classes. No template engine dependency.

**In scope:** Template rendering, system prompt caching.
**Out of scope:** Any API calls, any business logic.

---

### `prompts/user/system.md`

Defines the user simulator's permanent identity. Written once, never changes at runtime. Instructs the model to: produce a single realistic user message, match the tone and vocabulary of the given persona, stay on the given topic, vary question style (direct, indirect, confused, detailed, terse), never produce multiple questions in one turn, never produce an assistant response.

---

### `prompts/user/task.md`

Template with `{persona}`, `{topic}`, `{niches}`, `{history}` placeholders. Provides the per-call context. `{history}` is formatted as a readable prior conversation for multi-turn, empty string for single-turn.

---

### `prompts/teacher/system.md`

Template with single `{project_identity}` placeholder. Contains the assistant's full identity, use cases, and boundaries injected from the project files. Rendered once at pipeline init and cached. Instructs the teacher to: respond as the assistant described in the identity, use tools when needed, be accurate and helpful, match the appropriate tone.

---

### `prompts/validator/system.md`

Permanent validator identity. No placeholders. Defines what good looks like: accuracy, coherence, tone consistency, appropriate length, no hallucination, no template artifacts, proper tool use. Defines the scoring rubric for 1-10 scores. Defines binary validation criteria.

---

### `prompts/validator/task.md`

Template with `{teacher_system}` and `{sample}` placeholders. Used in validate mode. Instructs the validator to compare the sample against the teacher's system prompt (to check tone and boundary compliance) and return a JSON object: `{"accepted": bool, "reason": str}`.

---

### `prompts/validator/score_task.md`

Template with `{sample}` placeholder. Used in score mode. Instructs the validator to return a JSON object: `{"score": float, "reason": str}` where score is 1.0-10.0. Rubric: 9-10 is excellent, 7-8 is good, 5-6 is acceptable, below 5 is reject.

---

### `prompts/intake/gap_analysis.md`

System prompt for the gap analysis Opus call. Instructs Opus to: read the raw intake, identify what is missing or ambiguous (target users, use cases, tone, model to fine-tune, topics to cover, behaviors to prohibit), produce a structured internal analysis. Output is not shown to operator.

---

### `prompts/intake/questions.md`

System prompt for the question generation Opus call. Instructs Opus to: read the gap analysis, generate at most 10 questions, always include the four model-selection questions (user model, teacher model, validator model, fine-tune target model), phrase questions concisely for CLI presentation, order from most critical to least critical.

---

### `prompts/research/domain_research.md`

System prompt for the domain research Opus call. Instructs Opus to: search for real information about the domain described in the intake, find common user questions, find expert vocabulary, identify edge cases, identify what the assistant should refuse. Opus uses web search autonomously to gather this.

---

### `prompts/research/finetune_research.md`

System prompt for the fine-tune format research Opus call. Template with `{model_name}` placeholder. Instructs Opus to: search official documentation, Hugging Face model card, Unsloth documentation, Axolotl documentation, and TRL documentation for the target model. Find the exact chat template, special tokens, recommended data format, max sequence length, and any known fine-tuning quirks. Output must include enough detail for `export_dataset.py` to format data correctly without any hardcoded assumptions.

---

### `prompts/research/builder.md`

System prompt for the builder synthesis calls. Instructs Opus to: read research notes and intake, synthesise into the specific output file format described in the call, be concrete and specific (no generic advice), write as operational instructions that the pipeline will use directly.

---

### `tools/calculator.py`

Exposes one function: `calculate(expression: str) -> str`. Uses Python's `ast` module to safely parse and evaluate mathematical expressions. No `eval()`. No `exec()`. Supports arithmetic, basic math functions. Returns result as string or error message string. Never raises — always returns a string.

**In scope:** Safe arithmetic evaluation.
**Out of scope:** Any other computation, any I/O.

---

### `tools/web_search.py`

Exposes one async function: `search(query: str, num_results: int = 5) -> list[dict]`. Calls Brave Search API via `httpx`. Returns list of dicts with `title`, `url`, `snippet`. Reads API key from environment variable `SEARCH_API_KEY`. Never raises — returns empty list on error and logs to `logs/errors.jsonl`.

**In scope:** Web search via Brave API.
**Out of scope:** Any parsing, summarisation, or processing of results.

---

### `pipeline/single_turn.py`

Orchestrates single-turn sample generation. Exposes async function `generate_batch(batch_size: int, state: PipelineState, ...) -> list[Sample]`. For each sample in the batch:

1. Selects random persona and topic
2. Calls user client for user turn
3. Calls teacher client 5 times for candidates
4. Calls validator client to score each candidate
5. Keeps top 2 above min_score
6. Writes candidates to `data/candidates/single/`
7. Runs rule checks on kept candidates
8. Appends accepted to `data/clean/accepted.jsonl`
9. Updates PipelineState counters
10. Updates cost.json

**In scope:** Single-turn generation loop, rejection sampling, file writes.
**Out of scope:** Multi-turn logic, dedup, export.

---

### `pipeline/multi_turn.py`

Same as `single_turn.py` for multi-turn conversations. Contains `ConversationContext` dataclass (not a separate file): holds `messages: list[Message]` and `turn_count: int`. For each conversation, the context is built up turn by turn until `max_turns` is reached. The full conversation is then serialised as one multi-turn sample.

A new `ConversationContext` is created for each conversation. It is reset (recreated) after each complete conversation. It is not shared between conversations or between batches.

**In scope:** Multi-turn generation, ConversationContext lifecycle.
**Out of scope:** Single-turn logic, dedup, export.

---

### `pipeline/validate_sample.py`

Exposes `validate(sample: Sample, validator_client, teacher_system: str) -> ValidatorOutput`. Two stages:

Stage 1 — Rule checks (no API call): user turn non-empty, assistant turn non-empty, assistant turn length above minimum, no `{placeholder}` strings remaining in content, no string `None` in content.

Stage 2 — Semantic check (Anthropic API call): only if stage 1 passes. Calls `validator_client.validate()`.

Returns `ValidatorOutput` from whichever stage terminates the evaluation.

**In scope:** Two-stage sample validation.
**Out of scope:** Scoring (that's in the pipeline modules), generation.

---

### `pipeline/dedup.py`

Exposes `deduplicate(input_path: str, threshold: float, model_name: str) -> int`. Reads all samples from `accepted.jsonl`. Generates embeddings of user turns using `sentence-transformers`. Computes pairwise cosine similarity. Greedy dedup — first occurrence always kept, subsequent occurrences above threshold removed in-place. Rewrites `accepted.jsonl` with deduplicated samples. Returns count of removed samples.

All computation is local. No API calls. Uses `all-MiniLM-L6-v2` or whatever is in `configs/models.yaml` under `dedup_model`.

**In scope:** Embedding-based deduplication of accepted samples.
**Out of scope:** Validation, scoring, export.

---

### `pipeline/export_dataset.py`

Exposes `export(state: PipelineState)`. Reads `research/finetune_spec.md` and parses the data format specification. Reads all samples from `data/clean/accepted.jsonl`. Shuffles with seed from `dataset.yaml`. Splits into train/eval by ratio. Formats each sample according to the spec from `finetune_spec.md`. Writes `data/final/train.jsonl` and `data/final/eval.jsonl`. Writes `outputs/stats.json`.

This file has **zero hardcoded format knowledge**. It contains no string literals related to ChatML, ShareGPT, Alpaca, or any model format. All format details come from parsing `finetune_spec.md`. The parser must be robust — parse what the research phase wrote, handle variation in how the spec is expressed.

**In scope:** Format-agnostic export driven by finetune_spec.md.
**Out of scope:** Validation, generation, research.

---

### `pipeline/checkpoint.py`

Exposes `Checkpoint` class. Wraps read/write of `outputs/checkpoint.json`. Methods: `mark_phase_complete(phase: int)`, `is_phase_complete(phase: int) -> bool`, `update_counts(single: int, multi: int)`, `get_counts() -> tuple[int, int]`. Writes atomically — write to temp file then rename. Never corrupts checkpoint on crash.

**In scope:** Checkpoint read/write with crash safety.
**Out of scope:** Any pipeline logic.

---

### `pipeline/report.py`

Exposes `generate_report(state: PipelineState)`. Reads `outputs/stats.json` and `outputs/cost.json`. Generates `outputs/report.md` as a readable Markdown document. Covers: run ID, date, elapsed time, phase completion times, sample counts, acceptance rate, score distribution, dedup removals, cost breakdown, final dataset paths and sizes.

**In scope:** Report generation from existing output files.
**Out of scope:** Any computation or I/O beyond reading outputs and writing report.

---

## 9. Dashboard — Architecture and Patterns

### Core Pattern

The dashboard uses **Rich's `Live` context manager** to re-render a layout at a fixed refresh rate. The layout is rebuilt from a shared `PipelineState` dataclass on every refresh cycle. The pipeline never calls any Rich function directly — it only mutates `PipelineState`.

This separation means:
- The pipeline can be tested without a terminal
- The dashboard can be swapped (e.g. for a web UI) without touching the pipeline
- There are no race conditions — `PipelineState` is mutated synchronously in the async pipeline loop

### PipelineState

A `@dataclass` in `dashboard/dashboard.py`. All fields have defaults. No field raises on access. Every pipeline module that updates state receives the state object as a parameter — it is not a global.

Fields to include:
- `run_id: str` — the timestamp-based run identifier
- `start_time: float` — `time.time()` at run start
- `phases: dict[str, str]` — keys are phase names, values are `"pending"`, `"active"`, or `"done"`
- `single_completed: int`, `single_target: int`
- `multi_completed: int`, `multi_target: int`
- `accepted: int`, `rejected: int`, `errors: int`
- `current_batch: int`, `total_batches: int`
- `batch_candidates: int`, `batch_kept: int`, `batch_avg_score: float`
- `score_buckets: dict` — keys `"9-10"`, `"7-8"`, `"5-6"`, `"<5"`, values are counts
- `user_tokens: int`, `teacher_tokens: int`, `validator_tokens: int`
- `total_cost_usd: float`
- `samples_per_min: float`
- `activity: deque` — maxlen 10, each entry is a dict with `time`, `status`, `id`, `kind`, `detail`

Computed properties (no stored state, computed from stored fields):
- `elapsed: str` — `HH:MM:SS` from `start_time`
- `total_completed: int`
- `total_target: int`
- `eta: str` — estimated time remaining from `samples_per_min` and remaining count
- `acceptance_rate: float`

One method: `log(event: dict)` — stamps the event with current time and appends to `activity`.

### Layout Structure

Five panels arranged in a fixed layout:

```
┌─────────────────────── HEADER (run id, elapsed) ─────────────────────────┐
│                                                                            │
├── PHASES ──┬────── GENERATION PROGRESS ─────┬── REJECTION SAMPLING ──────┤
│            │                                │                             │
│            │                                │                             │
├────────────┴──────────────── COST ──────────┴─────────────────────────────┤
│                                                                            │
└──────────────────────── RECENT ACTIVITY ──────────────────────────────────┘
```

PHASES panel: 5 rows, one per phase. Icon: `○` pending, `●` active (yellow), `✓` done (green).
GENERATION PROGRESS: ASCII progress bars for single, multi, total. Accepted/rejected/error counts.
REJECTION SAMPLING: Current batch progress, average score, score distribution histogram.
COST: Per-role token usage and USD cost, throughput rate, ETA.
RECENT ACTIVITY: Rolling last-10 events. Accepted (green ✓), rejected (red ✗), error (yellow ⚠).

### Dashboard Class

`Dashboard` has three methods: `start()`, `stop()`, `refresh()`. `run.py` calls `start()` before phases begin and `stop()` after everything completes or on exception. Pipeline modules call `refresh()` after mutating state.

`refresh_per_second=2` in the `Live` constructor. The pipeline also calls explicit `refresh()` after significant state changes — batch completion, phase transition, error. Both mechanisms coexist.

### Dependency

`rich>=13.0.0` in `requirements.txt`. This is the only place Rich is imported. No other file in the project imports Rich.

---

## 10. Data Flow and File Relationships

```
                    OPERATOR INPUT
                         │
                    collect.py
                         │
                  raw_intake.md
                         │
                      gaps.py
                         │
              ┌──────────┴──────────┐
       enriched_intake.md      configs/models.yaml
                         │
                   researcher.py
               (Opus + web search)
                         │
                  research_notes.md
                         │
                    builder.py
                         │
          ┌──────────────┼─────────────────┐
       project/     finetune_spec.md   research_notes.md
          │               │
          │               │
     pipeline/ ←──────────┘
  (reads project/ + finetune_spec.md + models.yaml + dataset.yaml)
          │
          ├── single_turn.py ──► data/candidates/single/
          │                            │
          ├── multi_turn.py ──► data/candidates/multi/
          │                            │
          └── validate_sample.py ◄─────┘
                    │
             data/clean/accepted.jsonl
                    │
               dedup.py
                    │
          data/clean/accepted.jsonl (deduped)
                    │
          export_dataset.py ◄── finetune_spec.md
                    │
        ┌───────────┴────────────┐
   data/final/train.jsonl   data/final/eval.jsonl
                    │
               report.py
                    │
            outputs/report.md
```

### Which files read what:

| File | Reads |
|---|---|
| `intake/gaps.py` | `raw_intake.md`, `prompts/intake/gap_analysis.md`, `prompts/intake/questions.md` |
| `research/researcher.py` | `enriched_intake.md`, `configs/models.yaml`, `prompts/research/domain_research.md`, `prompts/research/finetune_research.md` |
| `research/builder.py` | `research_notes.md`, `enriched_intake.md`, `prompts/research/builder.md` |
| `clients/teacher.py` | `configs/models.yaml`, `configs/tools.yaml` |
| `clients/user.py` | `configs/models.yaml` |
| `clients/validator.py` | `configs/models.yaml` |
| `pipeline/single_turn.py` | `project/` (all), `configs/dataset.yaml` |
| `pipeline/multi_turn.py` | `project/` (all), `configs/dataset.yaml` |
| `pipeline/validate_sample.py` | None (receives data as parameters) |
| `pipeline/dedup.py` | `data/clean/accepted.jsonl`, `configs/models.yaml` |
| `pipeline/export_dataset.py` | `data/clean/accepted.jsonl`, `research/finetune_spec.md`, `configs/dataset.yaml` |
| `pipeline/report.py` | `outputs/stats.json`, `outputs/cost.json` |
| `prompts/render.py` | Any file in `prompts/` when called |

---

## 11. Code Standards

These are not suggestions. Claude Code must follow every one of these.

**Async throughout.** Every API call is async. `asyncio.gather()` is used for parallel calls where order doesn't matter. The pipeline's main loop is async. `run.py` calls `asyncio.run()` once at the top level.

**No global state except PipelineState.** `PipelineState` is instantiated once in `run.py` and passed explicitly to every function that needs it. No module-level mutable variables. No singleton patterns.

**No hardcoded strings for paths.** All file paths come from `configs/paths.yaml`. One helper function in a single shared location reads this file on first import and returns a dict. Path strings appear in exactly two places: `paths.yaml` and the one function that reads it.

**No hardcoded model names.** Model names only exist in `configs/models.yaml`. No string like `"claude-opus-4-6"` appears anywhere in `*.py` files.

**No hardcoded format strings for training data.** The training data format is determined entirely by `research/finetune_spec.md`. `export_dataset.py` parses this file at runtime.

**Every file has one responsibility.** If a file does two distinct things, it is two files.

**No dead code.** No functions that are not called. No imports that are not used. No variables that are set but never read.

**Errors are logged, not printed.** All errors append a structured dict to `logs/errors.jsonl`. No `print()` in any file except inside `dashboard/dashboard.py`'s Rich rendering.

**Retries with backoff.** API calls use exponential backoff up to `max_retries` from `dataset.yaml`. On final failure, the sample is skipped, the error is logged, and the state error counter is incremented.

**Atomic file writes.** Any file that is written incrementally (accepted.jsonl, cost.json, checkpoint.json) uses write-to-temp-then-rename to prevent corruption on crash.

**Type hints everywhere.** Every function has full type annotations on parameters and return types. No `Any` unless absolutely unavoidable with a comment explaining why.

**No over-engineering.** If a function is called once and takes three lines, it stays inline. A class is only created when there is genuine state to encapsulate and multiple methods that operate on that state. `ConversationContext` and `Checkpoint` are the only classes in the pipeline beyond Pydantic models and the `Dashboard`.

---

*End of specification. Build exactly this. Nothing more.*
