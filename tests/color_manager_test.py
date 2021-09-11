from __future__ import annotations

import pytest

from babi.color import Color
from babi.color_manager import _color_to_curses


@pytest.mark.parametrize(
    ('color', 'expected'),
    (
        (Color(0x00, 0x00, 0x00), (0, 0, 0)),
        (Color(0xff, 0xff, 0xff), (1000, 1000, 1000)),
        (Color(0x1e, 0x77, 0xd3), (117, 466, 827)),
    ),
)
def test_color_to_curses(color, expected):
    assert _color_to_curses(color) == expected
