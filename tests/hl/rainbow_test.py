from __future__ import annotations

import curses
from unittest import mock

import pytest

from babi.color import Color
from babi.color_manager import ColorManager
from babi.highlight import Region
from babi.hl.syntax import Syntax
from babi.theme import Theme


class FakeCurses:
    def __init__(self):
        self.colors = {}
        self.pairs = {}

    def bkgd(self, c, attr):
        pass

    def color_pair(self, n):
        return n << 8

    def init_color(self, n, r, g, b):
        self.colors[n] = (r, g, b)

    def init_pair(self, n, fg, bg):
        self.pairs[n] = (fg, bg)

    def can_change_color(self):
        return True


@pytest.fixture
def mock_curses():
    fake = FakeCurses()
    with (
        mock.patch.object(curses, 'color_pair', fake.color_pair),
        mock.patch.object(curses, 'init_color', fake.init_color),
        mock.patch.object(curses, 'init_pair', fake.init_pair),
        mock.patch.object(curses, 'can_change_color', fake.can_change_color),
        mock.patch.object(curses, 'COLORS', 256, create=True),
    ):
        yield fake


@pytest.fixture
def syntax_instance(mock_curses, make_grammars):
    cm = ColorManager.make()
    theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
    grammars = make_grammars({'scopeName': 'source.test', 'patterns': []})
    syntax = Syntax(grammars, theme, cm)
    syntax._init_screen(mock_curses)
    return syntax


def test_rainbow_brackets_basic(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')
    regions: tuple[Region, ...] = (Region(0, 6, ('source.test',)),)
    line = '((()))'
    stack = ()

    hls, new_stack = file_syntax._render_line(regions, line, stack)

    # We expect 6 HLs for the brackets
    assert len(hls) == 6
    assert new_stack == ()

    # Check colors cycle
    # We can check that attrs are different.
    attrs = [hl.attr for hl in hls]
    assert attrs[0] == attrs[5]  # Outer
    assert attrs[1] == attrs[4]  # Middle
    assert attrs[2] == attrs[3]  # Inner
    assert attrs[0] != attrs[1]
    assert attrs[1] != attrs[2]


def test_rainbow_brackets_mismatched(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')
    regions = (Region(0, 3, ('source.test',)),)
    line = '(()'
    stack = ()

    hls, new_stack = file_syntax._render_line(regions, line, stack)

    assert len(hls) == 3
    assert new_stack == ('(',)


def test_rainbow_brackets_ignore_string(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')

    # '()' inside string
    regions = (
        Region(0, 1, ('source.test', 'string')),
        Region(1, 3, ('source.test', 'string')),
        Region(3, 4, ('source.test', 'string')),
    )
    line = '"()"'
    stack = ()

    hls, new_stack = file_syntax._render_line(regions, line, stack)

    # Should be no highlights from rainbow brackets
    assert len(hls) == 0
    assert new_stack == ()


def test_mixed_brackets(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')
    regions = (Region(0, 4, ('source.test',)),)
    line = '[{}]'
    stack = ()

    hls, new_stack = file_syntax._render_line(regions, line, stack)

    assert len(hls) == 4
    attrs = [hl.attr for hl in hls]
    assert attrs[0] == attrs[3]  # []
    assert attrs[1] == attrs[2]  # {}
    assert attrs[0] != attrs[1]


def test_interleaved_lines(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')
    regions1 = (Region(0, 1, ('source.test',)),)
    line1 = '('

    hls1, stack1 = file_syntax._render_line(regions1, line1, ())
    assert len(hls1) == 1
    assert hls1[0].x == 0
    assert hls1[0].end == 1
    assert stack1 == ('(',)

    # Line 2: close paren
    regions2 = (Region(0, 1, ('source.test',)),)
    line2 = ')'
    hls2, stack2 = file_syntax._render_line(regions2, line2, stack1)
    assert len(hls2) == 1
    assert stack2 == ()
    assert hls1[0].attr == hls2[0].attr


def test_angular_brackets(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')

    # Case 1: Comparison (no special scope) - should NOT color
    regions = (Region(0, 6, ('source.test',)),)
    line = 'i < 10'
    hls, stack = file_syntax._render_line(regions, line, ())
    assert len(hls) == 0
    assert stack == ()

    # Case 2: Tag (special scope) - SHOULD color
    # <div matches
    regions_2tuple = (
        Region(0, 1, ('source.test', 'punctuation.definition.tag.begin')),
        Region(1, 4, ('source.test', 'entity.name.tag')),
    )
    line = '<div'
    hls, stack = file_syntax._render_line(regions_2tuple, line, ())
    assert len(hls) == 1
    assert hls[0].x == 0
    assert hls[0].end == 1
    assert stack == ('<',)

    # Case 3: Generic (special scope) - SHOULD color
    # Vector<int>
    regions_4tuple = (
        Region(0, 6, ('source.test', 'storage.type')),
        Region(6, 7, ('source.test', 'punctuation.definition.generic.begin')),
        Region(7, 10, ('source.test', 'storage.type')),
        Region(10, 11, ('source.test', 'punctuation.definition.generic.end')),
    )
    line = 'Vector<int>'
    hls, stack = file_syntax._render_line(regions_4tuple, line, ())
    assert len(hls) == 2
    assert hls[0].x == 6
    assert hls[0].end == 7
    # Second bracket should be colored and pop stack
    assert hls[1].x == 10
    assert hls[1].end == 11
    assert stack == ()


def test_mixed_text_and_brackets_single_region(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')
    # Single region with text and brackets
    regions = (Region(0, 8, ('source.test',)),)
    line = 'foo(bar)'
    hls, stack = file_syntax._render_line(regions, line, ())

    # Needs 4 HLs: foo, (, bar, )
    assert len(hls) == 4
    # foo (0-3)
    assert hls[0].x == 0
    assert hls[0].end == 3
    # ( (3-4) rainbow
    assert hls[1].x == 3
    assert hls[1].end == 4
    assert hls[1].attr != hls[0].attr
    # bar (4-7)
    assert hls[2].x == 4
    assert hls[2].end == 7
    # ) (7-8) rainbow
    assert hls[3].x == 7
    assert hls[3].end == 8

    assert stack == ()


def test_custom_theme_rainbow_colors(mock_curses, make_grammars):
    cm = ColorManager.make()
    # Define theme with custom rainbow colors
    theme_data = {
        'colors': {
            'editor.rainbow.0': '#111111',
            'editor.rainbow.1': '#222222',
        },
        'tokenColors': [],
    }
    theme = Theme.from_dct(theme_data)
    grammars = make_grammars({'scopeName': 'source.test', 'patterns': []})
    syntax = Syntax(grammars, theme, cm)
    syntax._init_screen(mock_curses)

    file_syntax = syntax.file_highlighter('test.txt', '')
    regions = (Region(0, 2, ('source.test',)),)
    line = '()'
    hls, stack = file_syntax._render_line(regions, line, ())
    assert len(hls) == 2

    assert len(syntax.theme.rainbow_colors) == 2
    assert syntax.theme.rainbow_colors[0].fg == Color.parse('#111111')


def test_mismatched_close_bracket_ignored(syntax_instance):
    file_syntax = syntax_instance.file_highlighter('test.txt', '')
    regions = (Region(0, 5, ('source.test',)),)
    line = '( ) ]'  # Open paren, close paren (match), close bracket (mismatch)
    hls, stack = file_syntax._render_line(regions, line, ())

    assert len(hls) == 5  # (, space, ), space, ]
    assert stack == ()
