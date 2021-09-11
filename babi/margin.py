from __future__ import annotations

import curses
from typing import NamedTuple


class Margin(NamedTuple):
    lines: int
    cols: int

    @property
    def header(self) -> bool:
        return self.lines > 2

    @property
    def footer(self) -> bool:
        return self.lines > 1

    @property
    def body_lines(self) -> int:
        return self.lines - self.header - self.footer

    @property
    def page_size(self) -> int:
        if self.body_lines <= 2:
            return 1
        else:
            return self.body_lines - 2

    @property
    def scroll_amount(self) -> int:
        # integer round up without banker's rounding (so 1/2 => 1 instead of 0)
        return int(self.lines / 2 + .5)

    @classmethod
    def from_current_screen(cls) -> Margin:
        return cls(curses.LINES, curses.COLS)
