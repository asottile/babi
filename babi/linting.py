from __future__ import annotations

import re
from typing import NamedTuple
from typing import Protocol

ERR_RE = re.compile(
    r'^(?P<filename>[^:]+):'
    r'(?P<lineno>[0-9]+):'
    r'(?:(?P<col_offset>[0-9]+):)?'
    r'(?P<msg>.*)$',
)


class Error(NamedTuple):
    filename: str
    lineno: int
    col_offset: int
    msg: str
    disabled: bool = False

    @property
    def line_idx(self) -> int:
        return self.lineno - 1

    @property
    def pos(self) -> tuple[int, int]:
        return self.lineno, self.col_offset

    def render(self) -> str:
        if self.disabled:
            return f'??:??: {self.msg}'
        else:
            return f'{self.lineno}:{self.col_offset}: {self.msg}'


def parse_generic_output(s: str) -> tuple[Error, ...]:
    ret = []
    for line in s.splitlines():
        match = ERR_RE.match(line)
        if match is not None:
            error = Error(
                filename=match['filename'],
                lineno=int(match['lineno']),
                col_offset=int(match['col_offset'] or '1'),
                msg=match['msg'].strip(),
            )
            ret.append(error)
    return tuple(ret)


class Linter(Protocol):
    def command(self, filename: str, scope: str) -> tuple[str, ...] | None: ...
    def parse(self, filename: str, output: str) -> tuple[Error, ...]: ...
