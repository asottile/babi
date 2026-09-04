from __future__ import annotations

import contextlib
import curses
from collections.abc import Callable
from collections.abc import Iterator
from typing import Any
from unittest import mock

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.highlight import Region
from babi.hl.bracket_match import BracketMatchHighlighter
from babi.hl.syntax import FileSyntax
from babi.hl.syntax import Syntax
from babi.theme import Theme


class FakeScreen:
    def __init__(self):
        self.attr = 0

    def bkgd(self, c, attr):
        assert c == ' '
        self.attr = attr


@contextlib.contextmanager
def patch_curses(
    *, n_colors: int = 256,
    can_change_color: bool = False,
) -> Iterator[None]:
    with mock.patch.object(curses, 'COLORS', n_colors, create=True):
        with mock.patch.multiple(
            curses,
            can_change_color=lambda: can_change_color,
            color_pair=lambda n: n << 8,
            init_color=lambda *args, **kwargs: None,
            init_pair=lambda *args, **kwargs: None,
        ):
            yield


def _syntax_and_file_hl(
    make_grammars: Callable[..., Any],
    theme: Theme,
) -> tuple[Syntax, FileSyntax]:
    grammars = make_grammars(
        {
            'scopeName': 'source.demo',
            'fileTypes': ['demo'],
            'patterns': [],
        },
    )
    syntax = Syntax(grammars, theme, ColorManager.make())
    return syntax, syntax.file_highlighter('foo.demo', '')


def test_getitem_without_register_callbacks_returns_empty(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(
            make_grammars,
            theme,
        )
        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )

        assert highlighter[0] == ()


def test_fake_screen_bkgd_smoke():
    scr = FakeScreen()
    scr.bkgd(' ', 123)
    assert scr.attr == 123


def test_no_syntax_state_returns_empty(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(
            make_grammars,
            theme,
        )
        buf = Buf(['()'])

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        # No highlight_until() called => _bracket_stacks is empty
        assert highlighter[0] == ()


def test_basic_matching_same_line_default_theme_fallback_attr(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['(foo)'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        highlighter.highlight_until(buf, 0)

        buf.y, buf.x = 0, 0
        hls = highlighter[0]
        assert len(hls) == 2
        assert all(hl.attr == (curses.A_BOLD | curses.A_REVERSE) for hl in hls)

        # second call should hit the cursor cache branch
        assert highlighter[0] == hls


def test_matching_cursor_on_close_bracket_uses_previous_open(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['(foo)'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 0, 4  # on ')'
        assert len(highlighter[0]) == 2


def test_multiline_matching_triggers_lazy_highlight_until(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)

        buf = Buf(['(', 'foo', ')'])
        # only highlight the first line; BracketMatchHighlighter should extend
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        assert highlighter[0] == (mock.ANY,)
        assert highlighter[2] == (mock.ANY,)


def test_non_code_scope_skips_brackets_in_string(make_grammars):
    with patch_curses():
        grammars = make_grammars(
            {
                'scopeName': 'source.demo',
                'fileTypes': ['demo'],
                'patterns': [{'match': r'"[^"]*"', 'name': 'string'}],
            },
        )
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        syntax = Syntax(grammars, theme, ColorManager.make())
        file_hl = syntax.file_highlighter('foo.demo', '')

        buf = Buf(['"("'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 1  # on '('

        assert highlighter[0] == ()


def test_angular_brackets_ignored_without_angular_scope(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['<>'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        assert highlighter[0] == ()


def test_angular_brackets_match_with_angular_scope(make_grammars):
    with patch_curses():
        grammars = make_grammars(
            {
                'scopeName': 'source.demo',
                'fileTypes': ['demo'],
                'patterns': [{
                    'match': r'[<>]',
                    'name': 'punctuation.definition.tag',
                }],
            },
        )
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        syntax = Syntax(grammars, theme, ColorManager.make())
        file_hl = syntax.file_highlighter('foo.demo', '')

        buf = Buf(['<>'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        assert len(highlighter[0]) == 2


def test_match_theme_non_default_style_does_not_use_reverse(make_grammars):
    with patch_curses():
        theme = Theme.from_dct(
            {
                'colors': {},
                'tokenColors': [
                    {'scope': 'match', 'settings': {'fontStyle': 'bold'}},
                ],
            },
        )
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)

        buf = Buf(['()'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        hls = highlighter[0]
        assert len(hls) == 2
        assert all(hl.attr & curses.A_BOLD for hl in hls)
        assert all(not (hl.attr & curses.A_REVERSE) for hl in hls)


def test_cache_invalidation_callbacks(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['(a)'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 0, 0
        assert len(highlighter[0]) == 2
        assert highlighter._cache_cursor == (0, 0)
        assert highlighter._cache_res is not None

        # set / del / ins should all clear the cache
        buf[0] = '(ab)'
        assert highlighter._cache_cursor is None
        assert highlighter._cache_res is None

        buf.insert(0, '')
        assert highlighter._cache_cursor is None
        assert highlighter._cache_res is None

        del buf[0]
        assert highlighter._cache_cursor is None
        assert highlighter._cache_res is None


def test_matching_returns_none_when_cursor_line_unhighlighted(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)

        # highlight only the first line
        buf = Buf(['(', '', ')'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 2, 0
        assert highlighter[2] == ()


def test_get_bracket_pair_handles_missing_hl_callable(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(
            make_grammars,
            theme,
        )
        buf = Buf(['()'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        # simulate syntax highlighting not ready
        file_hl._hl = None
        # force matching to bypass _find_matching() early return
        highlighter._find_matching = (  # type: ignore[method-assign]
            lambda buf: ('(', 0, 0, ')')
        )
        assert highlighter._get_bracket_pair(buf) is None


def test_get_bracket_pair_breaks_states_shorter_than_regions(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(
            make_grammars,
            theme,
        )
        buf = Buf(['', ''])

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        # make internal state inconsistent on purpose to cover the defensive
        # break path.
        file_hl.regions = [(), ()]
        file_hl._states = []
        file_hl._hl = lambda state, line, first: (state, ())

        highlighter._find_matching = (  # type: ignore[method-assign]
            lambda buf: ('(', 1, 0, ')')
        )
        assert highlighter._get_bracket_pair(buf) is None


def test_get_bracket_pair_skips_regions_before_open(make_grammars):
    with patch_curses():
        grammars = make_grammars(
            {
                'scopeName': 'source.demo',
                'fileTypes': ['demo'],
                'patterns': [{'match': r'foo', 'name': 'keyword'}],
            },
        )
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        syntax = Syntax(grammars, theme, ColorManager.make())
        file_hl = syntax.file_highlighter('foo.demo', '')

        buf = Buf(['foo(bar)'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 3

        assert len(highlighter[0]) == 2


def test_nested_matching_increments_nesting(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['(())'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0

        hls = highlighter[0]
        assert len(hls) == 2
        assert {hl.x for hl in hls} == {0, 3}


def test_open_char_angular_is_ignored_without_check_angular(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['<>'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        # force an angular open, but with regions that do not indicate angular
        highlighter._find_matching = (  # type: ignore[method-assign]
            lambda buf: ('<', 0, 0, '>')
        )

        assert highlighter._get_bracket_pair(buf) is None


def test_find_matching_uses_previous_line_stack_and_state(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['(', ')'])
        file_hl.highlight_until(buf, 2)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 1, 0
        assert highlighter._find_matching(buf) is not None


def test_find_matching_ignores_gt_when_not_angular(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['>'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 0, 1
        assert highlighter._find_matching(buf) is None


def test_find_matching_pops_matching_close_before_cursor(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['()'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 0, 2
        # cursor after the close means the open has been popped already
        assert highlighter._find_matching(buf) is None


def test_find_matching_returns_none_when_no_close_mapping(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['x'])
        file_hl.highlight_until(buf, 1)

        # Make a bogus "open" character that does not exist in pairs.
        file_hl.OPEN = {'x'}

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)

        buf.y, buf.x = 0, 1
        assert highlighter._find_matching(buf) is None


def test_get_bracket_pair_breaks_at_search_limit(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)

        # 1001 lines triggers the internal search_limit (1000)
        buf = Buf(['('] + [''] * 1000)

        # Avoid expensive highlighting: make internals consistent and return no
        # regions, so there is never a close bracket.
        file_hl.regions = [()] * len(buf)
        file_hl._states = [file_hl._compiler.root_state] * (len(buf) - 1)
        file_hl._hl = lambda state, line, first: (state, ())

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter._find_matching = (  # type: ignore[method-assign]
            lambda buf: ('(', 0, 0, ')')
        )
        assert highlighter._get_bracket_pair(buf) is None


def test_get_bracket_pair_skips_non_code_regions(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)
        buf = Buf(['xx'])

        file_hl.regions = [()]
        file_hl._hl = lambda state, line, first: (
            state,
            (Region(0, 2, ('string',)),),
        )

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter._find_matching = (  # type: ignore[method-assign]
            lambda buf: ('(', 0, 0, ')')
        )
        assert highlighter._get_bracket_pair(buf) is None


def test_find_matching_returns_none_when_hl_not_ready(make_grammars):
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(make_grammars, theme)

        buf = Buf(['()'])
        file_hl.highlight_until(buf, 1)

        # Bracket stacks exist, but syntax callable is missing.
        file_hl._hl = None

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 0
        assert highlighter._find_matching(buf) is None


def test_find_matching_close_with_empty_stack_branch(make_grammars):
    # Covers the branch where a close bracket is encountered before any open
    # bracket is in the current_stack.
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(
            make_grammars,
            theme,
        )

        buf = Buf([')'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 1

        assert highlighter._find_matching(buf) is None


def test_find_matching_mismatched_close_does_not_pop(make_grammars):
    # Covers the branch where a close bracket doesn't match the top-of-stack.
    with patch_curses():
        theme = Theme.from_dct({'colors': {}, 'tokenColors': []})
        _, file_hl = _syntax_and_file_hl(
            make_grammars,
            theme,
        )

        buf = Buf(['[)'])
        file_hl.highlight_until(buf, 1)

        highlighter = BracketMatchHighlighter(
            file_hl,
            theme,
            ColorManager.make(),
        )
        highlighter.register_callbacks(buf)
        buf.y, buf.x = 0, 2

        match = highlighter._find_matching(buf)
        assert match is not None
        open_char, open_y, open_x, close_char = match
        assert (open_char, open_y, open_x, close_char) == ('[', 0, 0, ']')
