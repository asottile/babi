from typing import NamedTuple
from typing import Tuple

from babi._types import Protocol
from babi.list_spy import SequenceNoSlice


class HL(NamedTuple):
    x: int
    end: int
    attr: int


HLs = Tuple[HL, ...]


class RegionsMapping(Protocol):
    def __getitem__(self, idx: int) -> HLs: ...


class FileHL(Protocol):
    @property
    def include_edge(self) -> bool: ...
    @property
    def regions(self) -> RegionsMapping: ...
    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None: ...
    def touch(self, lineno: int) -> None: ...


class HLFactory(Protocol):
    def file_highlighter(self, filename: str, first_line: str) -> FileHL: ...
    def blank_file_highlighter(self) -> FileHL: ...
