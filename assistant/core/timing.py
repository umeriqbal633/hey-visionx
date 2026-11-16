"""Per-command step timings (recording, STT, brain, skill), shown on screen and logged."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

# Steps that count toward "release -> action" (not recording, not waiting for a yes/no).
ACTION_STEPS = ("stt", "brain", "check", "skill")


class Timings:
    def __init__(self) -> None:
        self.steps: dict[str, float] = {}

    def add(self, name: str, seconds: float) -> None:
        self.steps[name] = self.steps.get(name, 0.0) + seconds

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.add(name, time.perf_counter() - start)

    @property
    def release_to_action(self) -> float:
        return sum(self.steps.get(s, 0.0) for s in ACTION_STEPS)

    def as_dict(self) -> dict[str, float]:
        data = {k: round(v, 3) for k, v in self.steps.items()}
        if self.steps:
            data["release_to_action"] = round(self.release_to_action, 3)
        return data

    def summary(self) -> str:
        if not self.steps:
            return ""
        parts = [f"{k} {v:.2f}s" for k, v in self.steps.items()]
        total = self.release_to_action
        flag = "" if total <= 3.0 else "  (over 3s target)"
        return "⏱ " + " | ".join(parts) + f" | release→action {total:.2f}s{flag}"
