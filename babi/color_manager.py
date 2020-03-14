import contextlib
import curses
from typing import Dict
from typing import NamedTuple
from typing import Tuple


class ColorManager(NamedTuple):
    raw_pairs: Dict[Tuple[int, int], int]

    def raw_color_pair(self, fg: int, bg: int) -> int:
        with contextlib.suppress(KeyError):
            return self.raw_pairs[(fg, bg)]

        n = self.raw_pairs[(fg, bg)] = len(self.raw_pairs) + 1
        curses.init_pair(n, fg, bg)
        return n

    @classmethod
    def make(cls) -> 'ColorManager':
        return cls({})
