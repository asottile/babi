from __future__ import annotations

from typing import NamedTuple
from typing import Protocol

from babi.buf import Buf


class HL(NamedTuple):
    x: int
    end: int
    attr: int


HLs = tuple[HL, ...]


class RegionsMapping(Protocol):
    def __getitem__(self, idx: int) -> HLs: ...


class FileHL(Protocol):
    @property
    def include_edge(self) -> bool: ...
    @property
    def regions(self) -> RegionsMapping: ...
    def highlight_until(self, lines: Buf, idx: int) -> None: ...
    def register_callbacks(self, buf: Buf) -> None: ...
