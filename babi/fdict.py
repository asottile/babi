from typing import Generic
from typing import Iterable
from typing import Mapping
from typing import TypeVar

TKey = TypeVar('TKey')
TValue = TypeVar('TValue')


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
