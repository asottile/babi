from __future__ import annotations

import curses
from typing import NamedTuple

from babi import color_kd
from babi.color import Color


def _color_to_curses(color: Color) -> tuple[int, int, int]:
    factor = 1000 / 255
    return int(color.r * factor), int(color.g * factor), int(color.b * factor)


class ColorManager(NamedTuple):
    colors: dict[Color, int]
    raw_pairs: dict[tuple[int, int], int]

    def init_color(self, color: Color) -> None:
        if curses.can_change_color():
            n = min(self.colors.values(), default=256) - 1
            self.colors[color] = n
            curses.init_color(n, *_color_to_curses(color))
        elif curses.COLORS >= 256:
            self.colors[color] = color_kd.nearest(color, color_kd.make_256())
        else:
            self.colors[color] = -1

    def color_pair(self, fg: Color | None, bg: Color | None) -> int:
        fg_i = self.colors[fg] if fg is not None else -1
        bg_i = self.colors[bg] if bg is not None else -1
        return self.raw_color_pair(fg_i, bg_i)

    def raw_color_pair(self, fg: int, bg: int) -> int:
        if curses.COLORS > 0:
            try:
                return self.raw_pairs[(fg, bg)]
            except KeyError:
                pass

            n = self.raw_pairs[(fg, bg)] = len(self.raw_pairs) + 1
            curses.init_pair(n, fg, bg)
            return n
        else:
            return 0

    @classmethod
    def make(cls) -> ColorManager:
        return cls({}, {})
