from __future__ import annotations

from typing import NamedTuple

# TODO: find a standard which defines these
# limited number of "named" colors
NAMED_COLORS = {'white': '#ffffff', 'black': '#000000'}


class Color(NamedTuple):
    r: int
    g: int
    b: int

    @classmethod
    def parse(cls, s: str) -> Color:
        if s.startswith('#') and len(s) >= 7:
            return cls(r=int(s[1:3], 16), g=int(s[3:5], 16), b=int(s[5:7], 16))
        elif s.startswith('#'):
            return cls.parse(f'#{s[1] * 2}{s[2] * 2}{s[3] * 2}')
        else:
            return cls.parse(NAMED_COLORS[s])
