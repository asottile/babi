from __future__ import annotations

import curses
import json

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode

THEME = json.dumps({
    'colors': {'background': '#00d700', 'foreground': '#303030'},
    'tokenColors': [{'scope': 'comment', 'settings': {'foreground': '#c00'}}],
})
SYNTAX = json.dumps({
    'scopeName': 'source.demo',
    'fileTypes': ['demo'],
    'patterns': [{'match': r'#.*$\n?', 'name': 'comment'}],
})


@pytest.fixture(autouse=True)
def theme_and_grammar(xdg_data_home, xdg_config_home):
    xdg_config_home.join('babi/theme.json').ensure().write(THEME)
    xdg_data_home.join('babi/grammar_v1/demo.json').ensure().write(SYNTAX)


@pytest.fixture
def demo(tmpdir):
    f = tmpdir.join('f.demo')
    f.write('# hello world\n')
    yield f


def test_retheme_signal(run, demo, xdg_config_home):
    def hot_modify_theme():
        new_theme = THEME.replace('#c00', '#00c')
        xdg_config_home.join('babi/theme.json').write(new_theme)

    with run(str(demo), term='screen-256color', width=40) as h, and_exit(h):
        h.await_text('hello world')

        for i, attr in enumerate([
                [(236, 40, curses.A_REVERSE)] * 40,         # header
                [(160, 40, 0)] * 13 + [(236, 40, 0)] * 27,  # # hello world
        ]):
            h.assert_screen_attr_equals(i, attr)

        h.run(hot_modify_theme)

        h.kill_usr1()

        # ensure that the reload worked
        h.press('A')
        h.await_text('A#')
        h.press('M-u')

        for i, attr in enumerate([
                [(236, 40, curses.A_REVERSE)] * 40,        # header
                [(20, 40, 0)] * 13 + [(236, 40, 0)] * 27,  # # hello world
        ]):
            h.assert_screen_attr_equals(i, attr)


def test_retheme_command_multiple_files(run, xdg_config_home, tmpdir):
    def hot_modify_theme():
        new_theme = THEME.replace('#c00', '#00c')
        xdg_config_home.join('babi/theme.json').write(new_theme)

    demo1 = tmpdir.join('t1.demo')
    demo1.write('# hello world')
    demo2 = tmpdir.join('t2.demo')
    demo2.write('# hello hello')

    with run(str(demo1), str(demo2), term='screen-256color', width=40) as h:
        with and_exit(h):
            h.await_text('hello world')

            for i, attr in enumerate([
                    [(236, 40, curses.A_REVERSE)] * 40,         # header
                    [(160, 40, 0)] * 13 + [(236, 40, 0)] * 27,  # # hello world
            ]):
                h.assert_screen_attr_equals(i, attr)

            h.run(hot_modify_theme)

            trigger_command_mode(h)
            h.press_and_enter(':retheme')
            h.await_text_missing(':retheme')

            for i, attr in enumerate([
                    [(236, 40, curses.A_REVERSE)] * 40,         # header
                    [(20, 40, 0)] * 13 + [(236, 40, 0)] * 27,   # # hello world
            ]):
                h.assert_screen_attr_equals(i, attr)

            # make sure the second file got re-themed as well
            h.press('^X')
            h.await_text('hello hello')

            for i, attr in enumerate([
                    [(236, 40, curses.A_REVERSE)] * 40,         # header
                    [(20, 40, 0)] * 13 + [(236, 40, 0)] * 27,   # # hello world
            ]):
                h.assert_screen_attr_equals(i, attr)
