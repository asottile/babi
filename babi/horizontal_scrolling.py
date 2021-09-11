from __future__ import annotations

import curses

from babi.cached_property import cached_property


def line_x(x: int, width: int) -> int:
    if x + 1 < width:
        return 0
    elif width == 1:
        return x
    else:
        margin = min(width - 3, 6)
        return (
            width - margin - 2 +
            (x + 1 - width) //
            (width - margin - 2) *
            (width - margin - 2)
        )


def scrolled_line(s: str, x: int, width: int) -> str:
    l_x = line_x(x, width)
    if l_x:
        s = f'«{s[l_x + 1:]}'
        if len(s) > width:
            return f'{s[:width - 1]}»'
        else:
            return s.ljust(width)
    elif len(s) > width:
        return f'{s[:width - 1]}»'
    else:
        return s.ljust(width)


class _CalcWidth:
    @cached_property
    def _window(self) -> curses._CursesWindow:
        return curses.newwin(1, 10)

    def wcwidth(self, c: str) -> int:
        self._window.addstr(0, 0, c)
        return self._window.getyx()[1]


wcwidth = _CalcWidth().wcwidth
del _CalcWidth
