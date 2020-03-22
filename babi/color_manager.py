import contextlib
import curses
from typing import Dict
from typing import NamedTuple
from typing import Optional
from typing import Tuple

from babi import color_kd
from babi.color import Color


def _color_to_curses(color: Color) -> Tuple[int, int, int]:
    factor = 1000 / 255
    return int(color.r * factor), int(color.g * factor), int(color.b * factor)


class ColorManager(NamedTuple):
    colors: Dict[Color, int]
    raw_pairs: Dict[Tuple[int, int], int]

    def init_color(self, color: Color) -> None:
        if curses.can_change_color():
            n = min(self.colors.values(), default=256) - 1
            self.colors[color] = n
            curses.init_color(n, *_color_to_curses(color))
        elif curses.COLORS >= 256:
            self.colors[color] = color_kd.nearest(color, color_kd.make_256())
        else:
            self.colors[color] = -1

    def color_pair(self, fg: Optional[Color], bg: Optional[Color]) -> int:
        fg_i = self.colors[fg] if fg is not None else -1
        bg_i = self.colors[bg] if bg is not None else -1
        return self.raw_color_pair(fg_i, bg_i)

    def raw_color_pair(self, fg: int, bg: int) -> int:
        with contextlib.suppress(KeyError):
            return self.raw_pairs[(fg, bg)]

        n = self.raw_pairs[(fg, bg)] = len(self.raw_pairs) + 1
        curses.init_pair(n, fg, bg)
        return n

    @classmethod
    def make(cls) -> 'ColorManager':
        return cls({}, {})
