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
    xdg_data_home.join('babi/textmate_syntax/demo.json').ensure().write(SYNTAX)


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
            h.assert_screen_attr_equals(i, attr)


def test_syntax_highlighting_does_not_highlight_arrows(run, tmpdir):
    f = tmpdir.join('f')
    f.write(
        f'#!/usr/bin/env demo\n'
        f'# l{"o" * 15}ng comment\n',
    )

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('loooo')
        h.assert_screen_attr_equals(2, [(243, 40, 0)] * 19 + [(236, 40, 0)])
