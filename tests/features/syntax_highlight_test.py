from __future__ import annotations

import curses
import json

import pytest

from testing.runner import and_exit


THEME = json.dumps({
    'colors': {'background': '#00d700', 'foreground': '#303030'},
    'tokenColors': [
        {'scope': 'comment', 'settings': {'foreground': '#767676'}},
        {
            'scope': 'diffremove',
            'settings': {'foreground': '#5f0000', 'background': '#ff5f5f'},
        },
        {'scope': 'tqs', 'settings': {'foreground': '#00005f'}},
        {'scope': 'qmark', 'settings': {'foreground': '#5f0000'}},
        {'scope': 'b', 'settings': {'fontStyle': 'bold'}},
        {'scope': 'i', 'settings': {'fontStyle': 'italic'}},
        {'scope': 'u', 'settings': {'fontStyle': 'underline'}},
    ],
})
SYNTAX = json.dumps({
    'scopeName': 'source.demo',
    'fileTypes': ['demo'],
    'firstLineMatch': '^#!/usr/bin/(env demo|demo)$',
    'patterns': [
        {'match': r'#.*$\n?', 'name': 'comment'},
        {'match': r'^-.*$\n?', 'name': 'diffremove'},
        {'begin': '"""', 'end': '"""', 'name': 'tqs'},
        {'match': r'\?', 'name': 'qmark'},
    ],
})
DEMO_S = '''\
- foo
# comment here
uncolored
"""tqs!
still more
"""
'''


@pytest.fixture(autouse=True)
def theme_and_grammar(xdg_data_home, xdg_config_home):
    xdg_config_home.join('babi/theme.json').ensure().write(THEME)
    xdg_data_home.join('babi/grammar_v1/demo.json').ensure().write(SYNTAX)


@pytest.fixture
def demo(tmpdir):
    f = tmpdir.join('f.demo')
    f.write(DEMO_S)
    yield f


def test_syntax_highlighting(run, demo):
    with run(str(demo), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('still more')
        for i, attr in enumerate([
                [(236, 40, curses.A_REVERSE)] * 20,        # header
                [(52, 203, 0)] * 5 + [(236, 40, 0)] * 15,  # - foo
                [(243, 40, 0)] * 14 + [(236, 40, 0)] * 6,  # # comment here
                [(236, 40, 0)] * 20,                       # uncolored
                [(17, 40, 0)] * 7 + [(236, 40, 0)] * 13,   # """tqs!
                [(17, 40, 0)] * 10 + [(236, 40, 0)] * 10,  # still more
                [(17, 40, 0)] * 3 + [(236, 40, 0)] * 17,   # """
        ]):
            h.assert_screen_attr_equal(i, attr)


def test_syntax_highlighting_does_not_highlight_arrows(run, tmpdir):
    f = tmpdir.join('f')
    f.write(
        f'#!/usr/bin/env demo\n'
        f'# l{"o" * 15}ng comment\n',
    )

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('loooo')
        h.assert_screen_attr_equal(2, [(243, 40, 0)] * 19 + [(236, 40, 0)])

        h.press('Down')
        h.press('^E')
        h.await_text_missing('loooo')
        expected = [(236, 40, 0)] + [(243, 40, 0)] * 15 + [(236, 40, 0)] * 4
        h.assert_screen_attr_equal(2, expected)


def test_syntax_highlighting_off_screen_does_not_crash(run, tmpdir):
    f = tmpdir.join('f.demo')
    f.write(f'"""a"""{"x" * 40}"""b"""')

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('"""a"""')
        h.assert_screen_attr_equal(1, [(17, 40, 0)] * 7 + [(236, 40, 0)] * 13)
        h.press('^E')
        h.await_text('"""b"""')
        expected = [(236, 40, 0)] * 11 + [(17, 40, 0)] * 7 + [(236, 40, 0)] * 2
        h.assert_screen_attr_equal(1, expected)


def test_syntax_highlighting_one_off_left_of_screen(run, tmpdir):
    f = tmpdir.join('f.demo')
    f.write(f'{"x" * 11}?123456789')

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('xxx?123')
        expected = [(236, 40, 0)] * 11 + [(52, 40, 0)] + [(236, 40, 0)] * 8
        h.assert_screen_attr_equal(1, expected)

        h.press('End')
        h.await_text_missing('?')
        h.assert_screen_attr_equal(1, [(236, 40, 0)] * 20)


def test_syntax_highlighting_to_edge_of_screen(run, tmpdir):
    f = tmpdir.join('f.demo')
    f.write(f'# {"x" * 18}')

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('# xxx')
        h.assert_screen_attr_equal(1, [(243, 40, 0)] * 20)


def test_syntax_highlighting_with_tabs(run, tmpdir):
    f = tmpdir.join('f.demo')
    f.write('\t# 12345678901234567890\n')

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('1234567890')
        expected = 4 * [(236, 40, 0)] + 15 * [(243, 40, 0)] + [(236, 40, 0)]
        h.assert_screen_attr_equal(1, expected)


def test_syntax_highlighting_tabs_after_line_creation(run, tmpdir):
    f = tmpdir.join('f')
    # trailing whitespace is used to trigger highlighting
    f.write('foo\n\txx \ny    \n')

    with run(str(f), term='screen-256color') as h, and_exit(h):
        # this looks weird, but it populates the width cache
        h.press('Down')
        h.press('Down')
        h.press('Down')

        # press enter after the tab
        h.press('Up')
        h.press('Up')
        h.press('Right')
        h.press('Right')
        h.press('Enter')

        h.await_text('foo\n    x\nx\ny\n')


def test_does_not_crash_with_no_color_support(run):
    with run(term='xterm-mono') as h, and_exit(h):
        pass
