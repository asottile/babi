import bisect
import curses
from typing import Tuple

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


def scrolled_line(
        s: str,
        positions: Tuple[int, ...],
        cursor_x: int,
        width: int,
) -> str:
    l_x = line_x(cursor_x, width)
    if l_x:
        l_x_min = l_x + 1
        start = bisect.bisect_left(positions, l_x_min)
        pad_left = '«' * (positions[start] - l_x)

        l_x_max = l_x + width
        if positions[-1] > l_x_max:
            end_max = l_x_max - 1
            end = bisect.bisect_left(positions, end_max)
            if positions[end] > end_max:
                end -= 1
            pad_right = '»' * (l_x_max - positions[end])
            return f'{pad_left}{s[start:end].expandtabs(4)}{pad_right}'
        else:
            return f'{pad_left}{s[start:]}'.ljust(width)
    elif positions[-1] > width:
        end_max = width - 1
        end = bisect.bisect_left(positions, end_max)
        if positions[end] > end_max:
            end -= 1
        pad_right = '»' * (width - positions[end])
        return f'{s[:end].expandtabs(4)}{pad_right}'
    else:
        return s.expandtabs(4).ljust(width)


class _CalcWidth:
    @cached_property
    def _window(self) -> 'curses._CursesWindow':
        return curses.newwin(1, 10)

    def wcwidth(self, c: str) -> int:
        self._window.addstr(0, 0, c)
        return self._window.getyx()[1]


wcwidth = _CalcWidth().wcwidth
del _CalcWidth
