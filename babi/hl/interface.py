from typing import Sequence
from typing import Tuple

from babi._types import Protocol
from babi._types import TypedDict
from babi.list_spy import SequenceNoSlice


class CursesRegion(TypedDict):
    x: int
    n: int
    color: int


CursesRegions = Tuple[CursesRegion, ...]


class FileHL(Protocol):
    @property
    def regions(self) -> Sequence[CursesRegions]: ...
    def highlight_until(self, lines: SequenceNoSlice, idx: int) -> None: ...
    def touch(self, lineno: int) -> None: ...


class HLFactory(Protocol):
    def get_file_highlighter(self, filename: str) -> FileHL: ...
    def get_blank_file_highlighter(self) -> FileHL: ...
