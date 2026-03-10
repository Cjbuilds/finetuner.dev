"""PipelineState dataclass and Rich Live dashboard. Only file that imports Rich."""

import time
from collections import deque
from dataclasses import dataclass, field

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class PipelineState:
    run_id: str = ""
    start_time: float = field(default_factory=time.time)
    phases: dict[str, str] = field(default_factory=lambda: {
        "Phase 1 — Intake: Collection": "pending",
        "Phase 2 — Intake: Gap Analysis": "pending",
        "Phase 3 — Research": "pending",
        "Phase 4 — Generation": "pending",
        "Phase 5 — Report": "pending",
    })
    single_completed: int = 0
    single_target: int = 0
    multi_completed: int = 0
    multi_target: int = 0
    accepted: int = 0
    rejected: int = 0
    errors: int = 0
    current_batch: int = 0
    total_batches: int = 0
    batch_candidates: int = 0
    batch_kept: int = 0
    batch_avg_score: float = 0.0
    score_buckets: dict[str, int] = field(default_factory=lambda: {
        "9-10": 0, "7-8": 0, "5-6": 0, "<5": 0,
    })
    user_tokens: int = 0
    teacher_tokens: int = 0
    validator_tokens: int = 0
    total_cost_usd: float = 0.0
    samples_per_min: float = 0.0
    activity: deque = field(default_factory=lambda: deque(maxlen=10))

    @property
    def elapsed(self) -> str:
        seconds = int(time.time() - self.start_time)
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def total_completed(self) -> int:
        return self.single_completed + self.multi_completed

    @property
    def total_target(self) -> int:
        return self.single_target + self.multi_target

    @property
    def eta(self) -> str:
        if self.samples_per_min <= 0 or self.total_target <= self.total_completed:
            return "--:--:--"
        remaining = self.total_target - self.total_completed
        minutes_left = remaining / self.samples_per_min
        seconds = int(minutes_left * 60)
        h, remainder = divmod(seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def acceptance_rate(self) -> float:
        total = self.accepted + self.rejected
        if total == 0:
            return 0.0
        return self.accepted / total

    def log(self, event: dict) -> None:
        event["time"] = time.strftime("%H:%M:%S")
        self.activity.append(event)


def _progress_bar(completed: int, target: int, width: int = 30) -> str:
    if target == 0:
        return "[" + " " * width + "] 0/0"
    ratio = min(completed / target, 1.0)
    filled = int(width * ratio)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {completed}/{target}"


def _build_header(state: PipelineState) -> Panel:
    text = Text()
    text.append(f"  Run: {state.run_id}", style="bold cyan")
    text.append(f"  |  Elapsed: {state.elapsed}", style="white")
    text.append(f"  |  ETA: {state.eta}", style="dim")
    return Panel(text, title="finetuner.dev", border_style="bright_blue")


def _build_phases(state: PipelineState) -> Panel:
    table = Table(show_header=False, show_edge=False, pad_edge=False, box=None)
    table.add_column(width=3)
    table.add_column()
    for name, status in state.phases.items():
        if status == "done":
            icon = Text("✓", style="green")
        elif status == "active":
            icon = Text("●", style="yellow")
        else:
            icon = Text("○", style="dim")
        table.add_row(icon, Text(name))
    return Panel(table, title="Phases", border_style="blue")


def _build_generation(state: PipelineState) -> Panel:
    lines = []
    lines.append(f"Single: {_progress_bar(state.single_completed, state.single_target)}")
    lines.append(f"Multi:  {_progress_bar(state.multi_completed, state.multi_target)}")
    lines.append(f"Total:  {_progress_bar(state.total_completed, state.total_target)}")
    lines.append("")
    lines.append(f"Accepted: {state.accepted}  Rejected: {state.rejected}  Errors: {state.errors}")
    return Panel("\n".join(lines), title="Generation Progress", border_style="blue")


def _build_rejection(state: PipelineState) -> Panel:
    lines = []
    if state.total_batches > 0:
        lines.append(f"Batch: {state.current_batch}/{state.total_batches}")
    lines.append(f"Candidates: {state.batch_candidates}  Kept: {state.batch_kept}")
    lines.append(f"Avg Score: {state.batch_avg_score:.1f}")
    lines.append("")
    lines.append("Score Distribution:")
    for bucket, count in state.score_buckets.items():
        bar = "█" * min(count, 40)
        lines.append(f"  {bucket:>4}: {bar} {count}")
    return Panel("\n".join(lines), title="Rejection Sampling", border_style="blue")


def _build_cost(state: PipelineState) -> Panel:
    lines = []
    lines.append(f"User tokens:      {state.user_tokens:>10,}")
    lines.append(f"Teacher tokens:   {state.teacher_tokens:>10,}")
    lines.append(f"Validator tokens: {state.validator_tokens:>10,}")
    lines.append(f"Total cost:       ${state.total_cost_usd:>9.4f}")
    lines.append(f"Throughput:       {state.samples_per_min:>9.1f} samples/min")
    return Panel("\n".join(lines), title="Cost", border_style="blue")


def _build_activity(state: PipelineState) -> Panel:
    lines = []
    for event in reversed(state.activity):
        t = event.get("time", "")
        status = event.get("status", "")
        detail = event.get("detail", "")
        sid = event.get("id", "")[:8]
        kind = event.get("kind", "")

        if status == "accepted":
            icon = "[green]✓[/green]"
        elif status == "rejected":
            icon = "[red]✗[/red]"
        elif status == "error":
            icon = "[yellow]⚠[/yellow]"
        else:
            icon = " "

        lines.append(f"  {icon} {t} [{kind}] {sid} {detail}")

    if not lines:
        lines.append("  Waiting for activity...")
    return Panel("\n".join(lines), title="Recent Activity", border_style="blue")


def _build_layout(state: PipelineState) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="middle", size=14),
        Layout(name="cost", size=9),
        Layout(name="activity", size=14),
    )
    layout["middle"].split_row(
        Layout(name="phases", ratio=1),
        Layout(name="generation", ratio=2),
        Layout(name="rejection", ratio=2),
    )
    layout["header"].update(_build_header(state))
    layout["phases"].update(_build_phases(state))
    layout["generation"].update(_build_generation(state))
    layout["rejection"].update(_build_rejection(state))
    layout["cost"].update(_build_cost(state))
    layout["activity"].update(_build_activity(state))
    return layout


class Dashboard:
    def __init__(self, state: PipelineState) -> None:
        self._state = state
        self._console = Console()
        self._live: Live | None = None

    def start(self) -> None:
        self._live = Live(
            _build_layout(self._state),
            console=self._console,
            refresh_per_second=2,
            screen=True,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def refresh(self) -> None:
        if self._live:
            self._live.update(_build_layout(self._state))
