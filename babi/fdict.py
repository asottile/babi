from __future__ import annotations

from typing import Generic
from typing import Iterable
from typing import Mapping
from typing import TypeVar

from babi._types import Protocol

TKey = TypeVar('TKey', contravariant=True)
TValue = TypeVar('TValue', covariant=True)


class FDict(Generic[TKey, TValue]):
    def __init__(self, dct: Mapping[TKey, TValue]) -> None:
        self._dct = dct

    def __getitem__(self, k: TKey) -> TValue:
        return self._dct[k]

    def __contains__(self, k: TKey) -> bool:
        return k in self._dct

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._dct})'

    def values(self) -> Iterable[TValue]:
        return self._dct.values()


class Indexable(Generic[TKey, TValue], Protocol):
    def __getitem__(self, key: TKey) -> TValue: ...


class FChainMap(Generic[TKey, TValue]):
    def __init__(self, *mappings: Indexable[TKey, TValue]) -> None:
        self._mappings = mappings

    def __getitem__(self, key: TKey) -> TValue:
        for mapping in reversed(self._mappings):
            try:
                return mapping[key]
            except KeyError:
                pass
        else:
            raise KeyError(key)
