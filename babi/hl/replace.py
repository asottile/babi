import contextlib
import curses
from typing import Generator
from typing import List

from babi.hl.interface import CursesRegion
from babi.hl.interface import CursesRegions
from babi.list_spy import SequenceNoSlice

HIGHLIGHT = curses.A_REVERSE | curses.A_DIM


class Replace:
    include_edge = True

    def __init__(self) -> None:
        self.regions: List[CursesRegions] = []

    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None:
        self.regions.extend(() for _ in range(len(self.regions), idx))

    def touch(self, lineno: int) -> None:
        """our highlight regions are populated in other ways"""

    @contextlib.contextmanager
    def region(self, y: int, x: int, n: int) -> Generator[None, None, None]:
        self.highlight_until((), y + 1)
        self.regions[y] = (CursesRegion(x=x, n=n, color=HIGHLIGHT),)
        try:
            yield
        finally:
            self.regions[y] = ()
