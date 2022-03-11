from __future__ import annotations

import curses

from babi.dim import Dim
from babi.prompt import PromptResult


class Status:
    def __init__(self) -> None:
        self._status = ''
        self._action_counter = -1

    def update(self, status: str) -> None:
        self._status = status
        self._action_counter = 25

    def clear(self) -> None:
        self._status = ''

    def draw(self, stdscr: curses._CursesWindow, dim: Dim) -> None:
        if dim.y > 0 or self._status:
            stdscr.insstr(dim.y, 0, ' ' * dim.width)
            if self._status:
                status = f' {self._status} '
                x = (dim.width - len(status)) // 2
                if x < 0:
                    x = 0
                    status = status.strip()
                stdscr.insstr(dim.y, x, status, curses.A_REVERSE)

    def tick(self, dim: Dim) -> None:
        # when the window is only 1-tall, hide the status quicker
        if dim.y > 0:
            self._action_counter -= 1
        else:
            self._action_counter -= 24
        if self._action_counter < 0:
            self.clear()

    def cancelled(self) -> PromptResult:
        self.update('cancelled')
        return PromptResult.CANCELLED
