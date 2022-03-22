from __future__ import annotations

import contextlib
import curses
from unittest import mock

import pytest

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.hl.interface import HL
from babi.hl.syntax import Syntax
from babi.theme import Color
from babi.theme import Theme


class FakeCurses:
    def __init__(self, *, n_colors, can_change_color):
        self._n_colors = n_colors
        self._can_change_color = can_change_color
        self.colors = {}
        self.pairs = {}

    def _curses__can_change_color(self):
        return self._can_change_color

    def _curses__init_color(self, n, r, g, b):
        self.colors[n] = (r, g, b)

    def _curses__init_pair(self, n, fg, bg):
        self.pairs[n] = (fg, bg)

    def _curses__color_pair(self, n):
        assert n == 0 or n in self.pairs
        return n << 8

    @classmethod
    @contextlib.contextmanager
    def patch(cls, **kwargs):
        fake = cls(**kwargs)
        with mock.patch.object(curses, 'COLORS', fake._n_colors, create=True):
            with mock.patch.multiple(
                    curses,
                    can_change_color=fake._curses__can_change_color,
                    color_pair=fake._curses__color_pair,
                    init_color=fake._curses__init_color,
                    init_pair=fake._curses__init_pair,
            ):
                yield fake


class FakeScreen:
    def __init__(self):
        self.attr = 0

    def bkgd(self, c, attr):
        assert c == ' '
        self.attr = attr


@pytest.fixture
def stdscr():
    return FakeScreen()


THEME = Theme.from_dct({
    'colors': {'foreground': '#cccccc', 'background': '#333333'},
    'tokenColors': [
        {'scope': 'string', 'settings': {'foreground': '#009900'}},
        {'scope': 'keyword', 'settings': {'background': '#000000'}},
        {'scope': 'keyword', 'settings': {'fontStyle': 'bold'}},
    ],
})


@pytest.fixture
def syntax(make_grammars):
    return Syntax(make_grammars(), THEME, ColorManager.make())


def test_init_screen_low_color(stdscr, syntax):
    with FakeCurses.patch(n_colors=16, can_change_color=False) as fake_curses:
        syntax._init_screen(stdscr)
    assert syntax.color_manager.colors == {
        Color.parse('#cccccc'): -1,
        Color.parse('#333333'): -1,
        Color.parse('#000000'): -1,
        Color.parse('#009900'): -1,
    }
    assert syntax.color_manager.raw_pairs == {(-1, -1): 1}
    assert fake_curses.colors == {}
    assert fake_curses.pairs == {1: (-1, -1)}
    assert stdscr.attr == 1 << 8


def test_init_screen_256_color(stdscr, syntax):
    with FakeCurses.patch(n_colors=256, can_change_color=False) as fake_curses:
        syntax._init_screen(stdscr)
    assert syntax.color_manager.colors == {
        Color.parse('#cccccc'): 252,
        Color.parse('#333333'): 236,
        Color.parse('#000000'): 16,
        Color.parse('#009900'): 28,
    }
    assert syntax.color_manager.raw_pairs == {(252, 236): 1}
    assert fake_curses.colors == {}
    assert fake_curses.pairs == {1: (252, 236)}
    assert stdscr.attr == 1 << 8


def test_init_screen_true_color(stdscr, syntax):
    with FakeCurses.patch(n_colors=256, can_change_color=True) as fake_curses:
        syntax._init_screen(stdscr)
    # weird colors happened with low color numbers so it counts down from max
    assert syntax.color_manager.colors == {
        Color.parse('#000000'): 255,
        Color.parse('#009900'): 254,
        Color.parse('#333333'): 253,
        Color.parse('#cccccc'): 252,
    }
    assert syntax.color_manager.raw_pairs == {(252, 253): 1}
    assert fake_curses.colors == {
        255: (0, 0, 0),
        254: (0, 600, 0),
        253: (200, 200, 200),
        252: (800, 800, 800),
    }
    assert fake_curses.pairs == {1: (252, 253)}
    assert stdscr.attr == 1 << 8


def test_lazily_instantiated_pairs(stdscr, syntax):
    # pairs are assigned lazily to avoid hard upper limit (256) on pairs
    with FakeCurses.patch(n_colors=256, can_change_color=False) as fake_curses:
        syntax._init_screen(stdscr)

        assert len(syntax.color_manager.raw_pairs) == 1
        assert len(fake_curses.pairs) == 1

        style = THEME.select(('string.python',))
        attr = style.attr(syntax.color_manager)
        assert attr == 2 << 8

        assert len(syntax.color_manager.raw_pairs) == 2
        assert len(fake_curses.pairs) == 2


def test_style_attributes_applied(stdscr, syntax):
    with FakeCurses.patch(n_colors=256, can_change_color=False):
        syntax._init_screen(stdscr)

        style = THEME.select(('keyword.python',))
        attr = style.attr(syntax.color_manager)
        assert attr == 2 << 8 | curses.A_BOLD


def test_syntax_highlight_cache_first_line(stdscr, make_grammars):
    with FakeCurses.patch(n_colors=256, can_change_color=False):
        grammars = make_grammars({
            'scopeName': 'source.demo',
            'fileTypes': ['demo'],
            'patterns': [{'match': r'\Aint', 'name': 'keyword'}],
        })
        syntax = Syntax(grammars, THEME, ColorManager.make())
        syntax._init_screen(stdscr)
        file_hl = syntax.file_highlighter('foo.demo', '')
        file_hl.highlight_until(Buf(['int', 'int']), 2)
        assert file_hl.regions == [
            (HL(0, 3, curses.A_BOLD | 2 << 8),),
            (),
        ]
