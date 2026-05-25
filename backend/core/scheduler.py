from __future__ import annotations

import asyncio
import time

from backend.config import SCRIPT_PATH, load_lines


class ScriptScheduler:
    def __init__(self) -> None:
        self.script_lines: list[str] = load_lines(SCRIPT_PATH)
        self.index: int = 0
        self.hold_until: float = 0.0
        self._interval: float = 8.0

    def reload_scripts(self) -> None:
        self.script_lines = load_lines(SCRIPT_PATH)

    def next_line(self) -> str | None:
        if time.time() < self.hold_until:
            return None
        if not self.script_lines:
            return None
        line = self.script_lines[self.index % len(self.script_lines)]
        self.index += 1
        return line

    def hold(self, seconds: float) -> None:
        self.hold_until = time.time() + seconds

    def current_position(self) -> int:
        return self.index

    async def run_ticker(self, on_tick: object) -> None:
        while True:
            await asyncio.sleep(self._interval)
            yield  # type: ignore[misc]
