"""Entry point. Orchestrates all phases with checkpoint recovery."""

import argparse
import asyncio
import math
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from configs import load_yaml, resolve_path
from dashboard.dashboard import Dashboard, PipelineState
from pipeline.checkpoint import Checkpoint


async def main() -> None:
    parser = argparse.ArgumentParser(description="finetuner.dev — synthetic SFT dataset pipeline")
    parser.add_argument("--from-phase", type=int, default=1, help="Start from phase N (prior phases must be complete)")
    args = parser.parse_args()

    # Create all required directories
    for dir_path in [
        "intake", "research", "project/personas", "project/topics",
        "data/raw/single", "data/raw/multi",
        "data/candidates/single", "data/candidates/multi",
        "data/clean", "data/final", "logs", "outputs", "configs",
    ]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    checkpoint = Checkpoint()

    # Validate --from-phase
    if args.from_phase > 1:
        for p in range(1, args.from_phase):
            if not checkpoint.is_phase_complete(p):
                print(f"Error: Phase {p} is not complete. Cannot start from phase {args.from_phase}.")
                sys.exit(1)

    # Create pipeline state
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    state = PipelineState(run_id=run_id, start_time=time.time())

    # Mark completed phases
    for p in range(1, 6):
        phase_names = {
            1: "Phase 1 — Intake: Collection",
            2: "Phase 2 — Intake: Gap Analysis",
            3: "Phase 3 — Research",
            4: "Phase 4 — Generation",
            5: "Phase 5 — Report",
        }
        if checkpoint.is_phase_complete(p):
            state.phases[phase_names[p]] = "done"

    dashboard = Dashboard(state)

    try:
        # Phase 1 — Collect
        if args.from_phase <= 1 and not checkpoint.is_phase_complete(1):
            state.phases["Phase 1 — Intake: Collection"] = "active"
            from intake.collect import run as collect_run
            await collect_run()
            state.phases["Phase 1 — Intake: Collection"] = "done"

        # Phase 2 — Gap Analysis
        if args.from_phase <= 2 and not checkpoint.is_phase_complete(2):
            state.phases["Phase 2 — Intake: Gap Analysis"] = "active"
            from intake.gaps import run as gaps_run
            await gaps_run()
            state.phases["Phase 2 — Intake: Gap Analysis"] = "done"

        # Start dashboard after interactive phases
        dashboard.start()

        # Phase 3 — Research
        if args.from_phase <= 3 and not checkpoint.is_phase_complete(3):
            state.phases["Phase 3 — Research"] = "active"
            dashboard.refresh()

            from research.researcher import run as researcher_run
            from research.builder import run as builder_run

            await researcher_run()
            await builder_run()

            state.phases["Phase 3 — Research"] = "done"
            dashboard.refresh()

        # Phase 4 — Generation, Validation, Dedup, Export
        if args.from_phase <= 4 and not checkpoint.is_phase_complete(4):
            state.phases["Phase 4 — Generation"] = "active"
            dashboard.refresh()

            dataset_config = load_yaml(resolve_path("dataset_config"))
            num_samples = dataset_config["num_samples"]
            single_ratio = dataset_config["single_ratio"]
            multi_ratio = dataset_config["multi_ratio"]
            batch_size = dataset_config["batch_size"]

            state.single_target = math.ceil(num_samples * single_ratio)
            state.multi_target = math.ceil(num_samples * multi_ratio)

            # Resume from checkpoint counts
            existing_single, existing_multi = checkpoint.get_counts()
            state.single_completed = existing_single
            state.multi_completed = existing_multi

            total_single_batches = math.ceil((state.single_target - state.single_completed) / batch_size)
            total_multi_batches = math.ceil((state.multi_target - state.multi_completed) / batch_size)
            state.total_batches = total_single_batches + total_multi_batches

            # Initialize clients
            from clients.user import UserClient
            from clients.teacher import TeacherClient
            from clients.validator import ValidatorClient

            user_client = UserClient()
            teacher_client = TeacherClient()
            validator_client = ValidatorClient()

            # Build teacher system prompt
            identity_path = resolve_path("identity")
            use_cases_path = resolve_path("use_cases")
            boundaries_path = resolve_path("boundaries")

            with open(identity_path) as f:
                identity = f.read()
            with open(use_cases_path) as f:
                use_cases = f.read()
            with open(boundaries_path) as f:
                boundaries = f.read()

            project_identity = f"{identity}\n\n## Use Cases\n{use_cases}\n\n## Boundaries\n{boundaries}"

            from prompts.render import render_system
            teacher_system = render_system("teacher", project_identity=project_identity)
            teacher_client.set_system_prompt(teacher_system)

            from pipeline.single_turn import generate_batch as single_batch
            from pipeline.multi_turn import generate_batch as multi_batch

            batch_num = 0
            generation_start = time.time()

            # Alternate between single and multi batches
            while (state.single_completed < state.single_target or
                   state.multi_completed < state.multi_target):

                batch_num += 1
                state.current_batch = batch_num
                state.batch_candidates = 0
                state.batch_kept = 0

                if state.single_completed < state.single_target:
                    remaining = state.single_target - state.single_completed
                    this_batch = min(batch_size, remaining)
                    await single_batch(
                        this_batch, state, user_client, teacher_client,
                        validator_client, teacher_system, dashboard,
                    )

                if state.multi_completed < state.multi_target:
                    remaining = state.multi_target - state.multi_completed
                    this_batch = min(batch_size, remaining)
                    await multi_batch(
                        this_batch, state, user_client, teacher_client,
                        validator_client, teacher_system, dashboard,
                    )

                # Update checkpoint
                checkpoint.update_counts(state.single_completed, state.multi_completed)

                # Update throughput
                elapsed_min = (time.time() - generation_start) / 60
                if elapsed_min > 0:
                    state.samples_per_min = state.total_completed / elapsed_min

                dashboard.refresh()

            # Dedup
            from pipeline.dedup import deduplicate
            models_config = load_yaml(resolve_path("models_config"))
            removed = deduplicate(
                resolve_path("accepted_samples"),
                dataset_config["dedup_threshold"],
                models_config["dedup_model"],
            )
            state.log({
                "status": "accepted",
                "id": "",
                "kind": "dedup",
                "detail": f"Removed {removed} duplicates",
            })
            dashboard.refresh()

            # Export
            from pipeline.export_dataset import export
            export(state)

            checkpoint.mark_phase_complete(4)
            state.phases["Phase 4 — Generation"] = "done"
            dashboard.refresh()

        # Phase 5 — Report
        if args.from_phase <= 5 and not checkpoint.is_phase_complete(5):
            state.phases["Phase 5 — Report"] = "active"
            dashboard.refresh()

            from pipeline.report import generate_report
            generate_report(state)

            state.phases["Phase 5 — Report"] = "done"
            dashboard.refresh()

    except KeyboardInterrupt:
        checkpoint.update_counts(state.single_completed, state.multi_completed)
    except Exception as e:
        from logs import log_error
        log_error({
            "module": "run",
            "error_type": type(e).__name__,
            "message": str(e),
        })
        checkpoint.update_counts(state.single_completed, state.multi_completed)
        raise
    finally:
        dashboard.stop()


if __name__ == "__main__":
    asyncio.run(main())
