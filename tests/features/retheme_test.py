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
    'patterns': [
        {'match': r'#.*$\n?', 'name': 'comment'},
        {'match': r'-.*$\n?', 'name': 'minus'},
    ],
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
            h.assert_screen_attr_equal(i, attr)

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
            h.assert_screen_attr_equal(i, attr)


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
                h.assert_screen_attr_equal(i, attr)

            h.run(hot_modify_theme)

            trigger_command_mode(h)
            h.press_and_enter(':retheme')
            h.await_text_missing(':retheme')

            for i, attr in enumerate([
                    [(236, 40, curses.A_REVERSE)] * 40,         # header
                    [(20, 40, 0)] * 13 + [(236, 40, 0)] * 27,   # # hello world
            ]):
                h.assert_screen_attr_equal(i, attr)

            # make sure the second file got re-themed as well
            h.press('^X')
            h.await_text('hello hello')

            for i, attr in enumerate([
                    [(236, 40, curses.A_REVERSE)] * 40,         # header
                    [(20, 40, 0)] * 13 + [(236, 40, 0)] * 27,   # # hello world
            ]):
                h.assert_screen_attr_equal(i, attr)


def test_retheme_bug(run, xdg_config_home, tmpdir):
    # this tests a complicated theme reloading bug triggered by:
    # - simple theme with not many colors
    # - reloads into a more complicated theme
    # - and then trailing whitespace is introduced

    # at the time of the fix the bug was a leak holding onto the old
    # highlighters and color manager through callbacks

    def hot_modify_theme():
        theme_json = json.dumps({
            'colors': {'background': '#00d700', 'foreground': '#303030'},
            'tokenColors': [
                {'scope': 'comment', 'settings': {'foreground': '#c00'}},
                {'scope': 'minus', 'settings': {'foreground': '#00c'}},
            ],
        })
        xdg_config_home.join('babi/theme.json').write(theme_json)

    f = tmpdir.join('t.demo')
    f.write('# hello\n- world\n')

    c_rev = [(236, 40, curses.A_REVERSE)]
    c_base = [(236, 40, 0)]
    c_comment = [(160, 40, 0)]
    c_minus = [(20, 40, 0)]
    c_ws = [(-1, 1, 0)]

    with run(str(f), term='screen-256color', width=80) as h, and_exit(h):
        h.await_text('# hello\n- world\n')

        for i, attr in enumerate([
                c_rev * 80,                    # header
                c_comment * 7 + c_base * 73,   # # hello
                c_base * 80,                   # - world
        ]):
            h.assert_screen_attr_equal(i, attr)

        h.run(hot_modify_theme)

        trigger_command_mode(h)
        h.press_and_enter(':retheme')
        h.await_text_missing(':retheme')

        for i, attr in enumerate([
                c_rev * 80,                    # header
                c_comment * 7 + c_base * 73,   # # hello
                c_minus * 7 + c_base * 73,     # - world
        ]):
            h.assert_screen_attr_equal(i, attr)

        # trigger trailing whitespace
        h.press_and_enter('hi ')
        h.await_text('hi')

        for i, attr in enumerate([
                c_rev * 80,                           # header
                c_base * 2 + c_ws * 1 + c_base * 77,  # hi<space>
                c_comment * 7 + c_base * 73,          # # hello
                c_minus * 7 + c_base * 73,            # - world
        ]):
            h.assert_screen_attr_equal(i, attr)
