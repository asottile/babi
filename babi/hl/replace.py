from __future__ import annotations

import collections
import contextlib
import curses
from typing import Generator

from babi.buf import Buf
from babi.hl.interface import HL
from babi.hl.interface import HLs


class Replace:
    include_edge = True

    def __init__(self) -> None:
        self.regions: dict[int, HLs] = collections.defaultdict(tuple)

    def highlight_until(self, lines: Buf, idx: int) -> None:
        """our highlight regions are populated in other ways"""

    def register_callbacks(self, buf: Buf) -> None:
        """our highlight regions are populated in other ways"""

    @contextlib.contextmanager
    def region(self, y: int, x: int, end: int) -> Generator[None, None, None]:
        # XXX: this assumes pair 1 is the background
        attr = curses.A_REVERSE | curses.A_DIM | curses.color_pair(1)
        self.regions[y] = (HL(x=x, end=end, attr=attr),)
        try:
            yield
        finally:
            del self.regions[y]
