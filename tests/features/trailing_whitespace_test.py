from __future__ import annotations

import curses

import pytest

from testing.runner import and_exit


@pytest.fixture(autouse=True)
def blank_theme(xdg_config_home):
    xdg_config_home.join('babi/theme.json').ensure().write('{}')


def test_trailing_whitespace_highlighting(run, tmpdir):
    f = tmpdir.join('f')
    f.write('0123456789     \n')

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('123456789')
        h.assert_screen_attr_equal(0, [(-1, -1, curses.A_REVERSE)] * 20)
        attrs = [(-1, -1, 0)] * 10 + [(-1, 1, 0)] * 5 + [(-1, -1, 0)] * 5
        h.assert_screen_attr_equal(1, attrs)


def test_trailing_whitespace_does_not_highlight_line_continuation(run, tmpdir):
    f = tmpdir.join('f')
    f.write(f'{" " * 30}\nhello\n')

    with run(str(f), term='screen-256color', width=20) as h, and_exit(h):
        h.await_text('hello')
        h.assert_screen_attr_equal(1, [(-1, 1, 0)] * 19 + [(-1, -1, 0)])
