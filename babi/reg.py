from __future__ import annotations

import functools
import re
from typing import Match

import onigurumacffi

_BACKREF_RE = re.compile(r'((?<!\\)(?:\\\\)*)\\([0-9]+)')


_FLAGS = {
    # (first_line, boundary)
    (False, False): (
        onigurumacffi.OnigSearchOption.NOT_END_STRING |
        onigurumacffi.OnigSearchOption.NOT_BEGIN_STRING |
        onigurumacffi.OnigSearchOption.NOT_BEGIN_POSITION
    ),
    (False, True): (
        onigurumacffi.OnigSearchOption.NOT_END_STRING |
        onigurumacffi.OnigSearchOption.NOT_BEGIN_STRING
    ),
    (True, False): (
        onigurumacffi.OnigSearchOption.NOT_END_STRING |
        onigurumacffi.OnigSearchOption.NOT_BEGIN_POSITION
    ),
    (True, True): onigurumacffi.OnigSearchOption.NOT_END_STRING,
}


class _Reg:
    def __init__(self, s: str) -> None:
        self._pattern = s
        self._reg = onigurumacffi.compile(self._pattern)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._pattern!r})'

    def search(
            self,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Match[str] | None:
        return self._reg.search(line, pos, flags=_FLAGS[first_line, boundary])

    def match(
            self,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Match[str] | None:
        return self._reg.match(line, pos, flags=_FLAGS[first_line, boundary])


class _RegSet:
    def __init__(self, *s: str) -> None:
        self._patterns = s
        self._set = onigurumacffi.compile_regset(*self._patterns)

    def __repr__(self) -> str:
        args = ', '.join(repr(s) for s in self._patterns)
        return f'{type(self).__name__}({args})'

    def search(
            self,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> tuple[int, Match[str] | None]:
        return self._set.search(line, pos, flags=_FLAGS[first_line, boundary])


def expand_escaped(match: Match[str], s: str) -> str:
    return _BACKREF_RE.sub(lambda m: f'{m[1]}{re.escape(match[int(m[2])])}', s)


make_reg = functools.lru_cache(maxsize=None)(_Reg)
make_regset = functools.lru_cache(maxsize=None)(_RegSet)
ERR_REG = make_reg('$ ^')
