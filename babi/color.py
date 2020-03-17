from typing import NamedTuple

# TODO: find a standard which defines these
# limited number of "named" colors
NAMED_COLORS = {'white': '#ffffff', 'black': '#000000'}


class Color(NamedTuple):
    r: int
    g: int
    b: int

    @classmethod
    def parse(cls, s: str) -> 'Color':
        if s.startswith('#'):
            return cls(r=int(s[1:3], 16), g=int(s[3:5], 16), b=int(s[5:7], 16))
        else:
            return cls.parse(NAMED_COLORS[s])
