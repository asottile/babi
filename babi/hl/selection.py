import collections
import curses
from typing import Dict
from typing import Optional
from typing import Tuple

from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.list_spy import SequenceNoSlice


class Selection:
    include_edge = True

    def __init__(self) -> None:
        self.regions: Dict[int, HLs] = collections.defaultdict(tuple)
        self.start: Optional[Tuple[int, int]] = None
        self.end: Optional[Tuple[int, int]] = None

    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None:
        if self.start is None or self.end is None:
            return

        # XXX: this assumes pair 1 is the background
        attr = curses.A_REVERSE | curses.A_DIM | curses.color_pair(1)
        (s_y, s_x), (e_y, e_x) = self.get()
        if s_y == e_y:
            self.regions[s_y] = (HL(x=s_x, end=e_x, attr=attr),)
        else:
            self.regions[s_y] = (
                HL(x=s_x, end=len(lines[s_y]) + 1, attr=attr),
            )
            for l_y in range(s_y + 1, e_y):
                self.regions[l_y] = (
                    HL(x=0, end=len(lines[l_y]) + 1, attr=attr),
                )
            self.regions[e_y] = (HL(x=0, end=e_x, attr=attr),)

    def touch(self, lineno: int) -> None:
        """our highlight regions are populated in other ways"""

    def get(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        assert self.start is not None and self.end is not None
        if self.start < self.end:
            return self.start, self.end
        else:
            return self.end, self.start

    def clear(self) -> None:
        if self.start is not None and self.end is not None:
            (s_y, _), (e_y, _) = self.get()
            for l_y in range(s_y, e_y + 1):
                del self.regions[l_y]
        self.start = self.end = None

    def set(self, s_y: int, s_x: int, e_y: int, e_x: int) -> None:
        self.clear()
        self.start, self.end = (s_y, s_x), (e_y, e_x)
