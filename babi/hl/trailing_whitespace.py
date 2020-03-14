import curses
from typing import List
from typing import NamedTuple

from babi.color_manager import ColorManager
from babi.hl.interface import CursesRegion
from babi.hl.interface import CursesRegions
from babi.list_spy import SequenceNoSlice


class FileTrailingWhitespace:
    def __init__(self, color_manager: ColorManager) -> None:
        self._color_manager = color_manager

        self.regions: List[CursesRegions] = []

    def _trailing_ws(self, line: str) -> CursesRegions:
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
            return (CursesRegion(x=i, n=len(line) - i, color=attr),)

    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None:
        for i in range(len(self.regions), idx):
            self.regions.append(self._trailing_ws(lines[i]))

    def touch(self, lineno: int) -> None:
        del self.regions[lineno:]


class TrailingWhitespace(NamedTuple):
    color_manager: ColorManager

    def get_file_highlighter(self, filename: str) -> FileTrailingWhitespace:
        # no file-specific behaviour
        return self.get_blank_file_highlighter()

    def get_blank_file_highlighter(self) -> FileTrailingWhitespace:
        return FileTrailingWhitespace(self.color_manager)
