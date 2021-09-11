from __future__ import annotations

import sys

if sys.version_info >= (3, 8):  # pragma: no cover (>=py38)
    from functools import cached_property
else:  # pragma: no cover (<py38)
    from typing import Callable
    from typing import Generic
    from typing import TypeVar

    TSelf = TypeVar('TSelf')
    TRet = TypeVar('TRet')

    class cached_property(Generic[TSelf, TRet]):
        def __init__(self, func: Callable[[TSelf], TRet]) -> None:
            self._func = func

        def __get__(
                self,
                instance: TSelf | None,
                owner: type[TSelf] | None = None,
        ) -> TRet:
            assert instance is not None
            ret = instance.__dict__[self._func.__name__] = self._func(instance)
            return ret
