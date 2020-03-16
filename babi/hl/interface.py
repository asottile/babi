from typing import Tuple

from babi._types import Protocol
from babi._types import TypedDict
from babi.list_spy import SequenceNoSlice


class CursesRegion(TypedDict):
    x: int
    n: int
    color: int


CursesRegions = Tuple[CursesRegion, ...]


class RegionsMapping(Protocol):
    def __getitem__(self, idx: int) -> CursesRegions: ...


class FileHL(Protocol):
    @property
    def include_edge(self) -> bool: ...
    @property
    def regions(self) -> RegionsMapping: ...
    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None: ...
    def touch(self, lineno: int) -> None: ...


class HLFactory(Protocol):
    def get_file_highlighter(self, filename: str) -> FileHL: ...
    def get_blank_file_highlighter(self) -> FileHL: ...
