import curses
from typing import NamedTuple


class Margin(NamedTuple):
    header: bool
    footer: bool

    @property
    def body_lines(self) -> int:
        return curses.LINES - self.header - self.footer

    @property
    def page_size(self) -> int:
        if self.body_lines <= 2:
            return 1
        else:
            return self.body_lines - 2

    @classmethod
    def from_current_screen(cls) -> 'Margin':
        if curses.LINES == 1:
            return cls(header=False, footer=False)
        elif curses.LINES == 2:
            return cls(header=False, footer=True)
        else:
            return cls(header=True, footer=True)
