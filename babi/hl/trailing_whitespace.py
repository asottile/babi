from __future__ import annotations

import curses

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.hl.interface import HL
from babi.hl.interface import HLs


class TrailingWhitespace:
    include_edge = False

    def __init__(self, color_manager: ColorManager) -> None:
        self._color_manager = color_manager

        self.regions: list[HLs] = []

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

    def _set_cb(self, lines: Buf, idx: int, victim: str) -> None:
        if idx < len(self.regions):
            self.regions[idx] = self._trailing_ws(lines[idx])

    def _del_cb(self, lines: Buf, idx: int, victim: str) -> None:
        if idx < len(self.regions):
            del self.regions[idx]

    def _ins_cb(self, lines: Buf, idx: int) -> None:
        if idx < len(self.regions):
            self.regions.insert(idx, self._trailing_ws(lines[idx]))

    def register_callbacks(self, buf: Buf) -> None:
        buf.add_set_callback(self._set_cb)
        buf.add_del_callback(self._del_cb)
        buf.add_ins_callback(self._ins_cb)

    def highlight_until(self, lines: Buf, idx: int) -> None:
        for i in range(len(self.regions), idx):
            self.regions.append(self._trailing_ws(lines[i]))
