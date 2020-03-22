import functools
import re
from typing import Match
from typing import Optional
from typing import Tuple

import onigurumacffi

from babi.cached_property import cached_property

_BACKREF_RE = re.compile(r'((?<!\\)(?:\\\\)*)\\([0-9]+)')


def _replace_esc(s: str, chars: str) -> str:
    """replace the given escape sequences of `chars` with \\uffff"""
    for c in chars:
        if f'\\{c}' in s:
            break
    else:
        return s

    b = []
    i = 0
    length = len(s)
    while i < length:
        try:
            sbi = s.index('\\', i)
        except ValueError:
            b.append(s[i:])
            break
        if sbi > i:
            b.append(s[i:sbi])
        b.append('\\')
        i = sbi + 1
        if i < length:
            if s[i] in chars:
                b.append('\uffff')
            else:
                b.append(s[i])
        i += 1
    return ''.join(b)


class _Reg:
    def __init__(self, s: str) -> None:
        self._pattern = s

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._pattern!r})'

    @cached_property
    def _reg(self) -> onigurumacffi._Pattern:
        return onigurumacffi.compile(self._pattern)

    @cached_property
    def _reg_no_A(self) -> onigurumacffi._Pattern:
        return onigurumacffi.compile(_replace_esc(self._pattern, 'A'))

    @cached_property
    def _reg_no_G(self) -> onigurumacffi._Pattern:
        return onigurumacffi.compile(_replace_esc(self._pattern, 'G'))

    @cached_property
    def _reg_no_A_no_G(self) -> onigurumacffi._Pattern:
        return onigurumacffi.compile(_replace_esc(self._pattern, 'AG'))

    def _get_reg(
            self,
            first_line: bool,
            boundary: bool,
    ) -> onigurumacffi._Pattern:
        if boundary:
            if first_line:
                return self._reg
            else:
                return self._reg_no_A
        else:
            if first_line:
                return self._reg_no_G
            else:
                return self._reg_no_A_no_G

    def search(
            self,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Match[str]]:
        return self._get_reg(first_line, boundary).search(line, pos)

    def match(
            self,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Optional[Match[str]]:
        return self._get_reg(first_line, boundary).match(line, pos)


class _RegSet:
    def __init__(self, *s: str) -> None:
        self._patterns = s

    def __repr__(self) -> str:
        args = ', '.join(repr(s) for s in self._patterns)
        return f'{type(self).__name__}({args})'

    @cached_property
    def _set(self) -> onigurumacffi._RegSet:
        return onigurumacffi.compile_regset(*self._patterns)

    @cached_property
    def _set_no_A(self) -> onigurumacffi._RegSet:
        patterns = (_replace_esc(p, 'A') for p in self._patterns)
        return onigurumacffi.compile_regset(*patterns)

    @cached_property
    def _set_no_G(self) -> onigurumacffi._RegSet:
        patterns = (_replace_esc(p, 'G') for p in self._patterns)
        return onigurumacffi.compile_regset(*patterns)

    @cached_property
    def _set_no_A_no_G(self) -> onigurumacffi._RegSet:
        patterns = (_replace_esc(p, 'AG') for p in self._patterns)
        return onigurumacffi.compile_regset(*patterns)

    def search(
            self,
            line: str,
            pos: int,
            first_line: bool,
            boundary: bool,
    ) -> Tuple[int, Optional[Match[str]]]:
        if boundary:
            if first_line:
                return self._set.search(line, pos)
            else:
                return self._set_no_A.search(line, pos)
        else:
            if first_line:
                return self._set_no_G.search(line, pos)
            else:
                return self._set_no_A_no_G.search(line, pos)


def expand_escaped(match: Match[str], s: str) -> str:
    return _BACKREF_RE.sub(lambda m: f'{m[1]}{re.escape(match[int(m[2])])}', s)


make_reg = functools.lru_cache(maxsize=None)(_Reg)
make_regset = functools.lru_cache(maxsize=None)(_RegSet)
ERR_REG = make_reg(')this pattern always triggers an error when used(')
