import functools
import sys
from typing import Callable
from typing import Iterator
from typing import List

from babi._types import Protocol


class SequenceNoSlice(Protocol):
    def __len__(self) -> int: ...
    def __getitem__(self, idx: int) -> str: ...

    def __iter__(self) -> Iterator[str]:
        for i in range(len(self)):
            yield self[i]


class MutableSequenceNoSlice(SequenceNoSlice, Protocol):
    def __setitem__(self, idx: int, val: str) -> None: ...
    def __delitem__(self, idx: int) -> None: ...
    def insert(self, idx: int, val: str) -> None: ...

    def append(self, val: str) -> None:
        self.insert(len(self), val)

    def pop(self, idx: int = -1) -> str:
        victim = self[idx]
        del self[idx]
        return victim


def _del(lst: MutableSequenceNoSlice, *, idx: int) -> None:
    del lst[idx]


def _set(lst: MutableSequenceNoSlice, *, idx: int, val: str) -> None:
    lst[idx] = val


def _ins(lst: MutableSequenceNoSlice, *, idx: int, val: str) -> None:
    lst.insert(idx, val)


class ListSpy(MutableSequenceNoSlice):
    def __init__(self, lst: MutableSequenceNoSlice) -> None:
        self._lst = lst
        self._undo: List[Callable[[MutableSequenceNoSlice], None]] = []
        self.min_line_touched = sys.maxsize

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._lst})'

    def __len__(self) -> int:
        return len(self._lst)

    def __getitem__(self, idx: int) -> str:
        return self._lst[idx]

    def __setitem__(self, idx: int, val: str) -> None:
        self._undo.append(functools.partial(_set, idx=idx, val=self._lst[idx]))
        self.min_line_touched = min(idx, self.min_line_touched)
        self._lst[idx] = val

    def __delitem__(self, idx: int) -> None:
        if idx < 0:
            idx %= len(self)
        self._undo.append(functools.partial(_ins, idx=idx, val=self._lst[idx]))
        self.min_line_touched = min(idx, self.min_line_touched)
        del self._lst[idx]

    def insert(self, idx: int, val: str) -> None:
        if idx < 0:
            idx %= len(self)
        self._undo.append(functools.partial(_del, idx=idx))
        self.min_line_touched = min(idx, self.min_line_touched)
        self._lst.insert(idx, val)

    def undo(self, lst: MutableSequenceNoSlice) -> None:
        for fn in reversed(self._undo):
            fn(lst)

    @property
    def has_modifications(self) -> bool:
        return bool(self._undo)
