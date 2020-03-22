import curses
from typing import List

from babi.color_manager import ColorManager
from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.list_spy import SequenceNoSlice


class TrailingWhitespace:
    include_edge = False

    def __init__(self, color_manager: ColorManager) -> None:
        self._color_manager = color_manager

        self.regions: List[HLs] = []

    def _trailing_ws(self, line: str) -> HLs:
        if not line:
            return ()

        i = len(line)
        while i > 0 and line[i - 1].isspace():
            i -= 1

        if i == len(line):
            return ()
        else:
            pair = self._color_manager.raw_color_pair(-1, curses.COLOR_RED)
            attr = curses.color_pair(pair)
            return (HL(x=i, end=len(line), attr=attr),)

    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None:
        for i in range(len(self.regions), idx):
            self.regions.append(self._trailing_ws(lines[i]))

    def touch(self, lineno: int) -> None:
        del self.regions[lineno:]
