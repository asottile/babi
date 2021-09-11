from __future__ import annotations

import pytest

from testing.runner import and_exit


def test_search_wraps(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.press('Down')
        h.await_cursor_position(x=0, y=3)
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('^line_0$')
        h.await_text('search wrapped')
        h.await_cursor_position(x=0, y=1)


def test_search_find_next_line(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.await_cursor_position(x=0, y=1)
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('^line_')
        h.await_cursor_position(x=0, y=2)


def test_search_find_later_in_line(run):
    with run() as h, and_exit(h):
        h.press_and_enter('lol')
        h.press('Up')
        h.press('Right')
        h.await_cursor_position(x=1, y=1)

        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('l')
        h.await_cursor_position(x=2, y=1)


def test_search_only_one_match_already_at_that_match(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('^line_1$')
        h.await_text('this is the only occurrence')
        h.await_cursor_position(x=0, y=2)


def test_search_sets_x_hint_properly(run, tmpdir):
    f = tmpdir.join('f')
    contents = '''\
beginning_line

match me!
'''
    f.write(contents)
    with run(str(f)) as h, and_exit(h):
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('me!')
        h.await_cursor_position(x=6, y=3)
        h.press('Up')
        h.press('Up')
        h.await_cursor_position(x=6, y=1)


def test_search_not_found(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('this will not match')
        h.await_text('no matches')
        h.await_cursor_position(x=0, y=1)


def test_search_invalid_regex(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('invalid(regex')
        h.await_text("invalid regex: 'invalid(regex'")


@pytest.mark.parametrize('key', ('Enter', '^C'))
def test_search_cancel(run, ten_lines, key):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.await_text('search:')
        h.press(key)
        h.await_text('cancelled')


def test_search_repeated_search(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.press('line')
        h.await_text('search: line')
        h.press('Enter')
        h.await_cursor_position(x=0, y=2)

        h.press('^W')
        h.await_text('search [line]:')
        h.press('Enter')
        h.await_cursor_position(x=0, y=3)


def test_search_history_recorded(run):
    with run() as h, and_exit(h):
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('asdf')
        h.await_text('no matches')

        h.press('^W')
        h.press('Up')
        h.await_text('search [asdf]: asdf')
        h.press('BSpace')
        h.press('test')
        h.await_text('search [asdf]: asdtest')
        h.press('Down')
        h.await_text_missing('asdtest')
        h.press('Down')  # can't go past the end
        h.press('Up')
        h.await_text('asdtest')
        h.press('Up')  # can't go past the beginning
        h.await_text('asdtest')
        h.press('Enter')
        h.await_text('no matches')

        h.press('^W')
        h.press('Up')
        h.await_text('search [asdtest]: asdtest')
        h.press('Up')
        h.await_text('search [asdtest]: asdf')
        h.press('^C')


def test_search_history_duplicates_dont_repeat(run):
    with run() as h, and_exit(h):
        h.press('^W')
        h.await_text('search:')
        h.press_and_enter('search1')
        h.await_text('no matches')

        h.press('^W')
        h.await_text('search [search1]:')
        h.press_and_enter('search2')
        h.await_text('no matches')

        h.press('^W')
        h.await_text('search [search2]:')
        h.press_and_enter('search2')
        h.await_text('no matches')

        h.press('^W')
        h.press('Up')
        h.await_text('search2')
        h.press('Up')
        h.await_text('search1')
        h.press('Enter')


def test_search_history_is_saved_between_sessions(run, xdg_data_home):
    with run() as h, and_exit(h):
        h.press('^W')
        h.press_and_enter('search1')
        h.press('^W')
        h.press_and_enter('search2')

    contents = xdg_data_home.join('babi/history/search').read()
    assert contents == 'search1\nsearch2\n'

    with run() as h, and_exit(h):
        h.press('^W')
        h.press('Up')
        h.await_text('search: search2')
        h.press('Up')
        h.await_text('search: search1')
        h.press('Enter')


def test_search_multiple_sessions_append_to_history(run, xdg_data_home):
    xdg_data_home.join('babi/history/search').ensure().write(
        'orig\n'
        'history\n',
    )

    with run() as h1, and_exit(h1):
        with run() as h2, and_exit(h2):
            h2.press('^W')
            h2.press_and_enter('h2 history')
        h1.press('^W')
        h1.press_and_enter('h1 history')

    contents = xdg_data_home.join('babi/history/search').read()
    assert contents == (
        'orig\n'
        'history\n'
        'h2 history\n'
        'h1 history\n'
    )


def test_search_default_same_as_prev_history(run, xdg_data_home, ten_lines):
    xdg_data_home.join('babi/history/search').ensure().write('line\n')

    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.press_and_enter('line')
        h.await_cursor_position(x=0, y=2)
        h.press('^W')
        h.await_text('search [line]:')
        h.press('Enter')
        h.await_cursor_position(x=0, y=3)


@pytest.mark.parametrize('key', ('BSpace', '^H'))
def test_search_reverse_search_history_backspace(run, xdg_data_home, key):
    xdg_data_home.join('babi/history/search').ensure().write(
        'line_5\n'
        'line_3\n'
        'line_1\n',
    )
    with run() as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.await_text('search(reverse-search)``:')
        h.press('linea')
        h.await_text('search(failed reverse-search)`linea`: line_1')
        h.press(key)
        h.await_text('search(reverse-search)`line`: line_1')
        h.press('^C')


def test_search_reverse_search_history(run, xdg_data_home, ten_lines):
    xdg_data_home.join('babi/history/search').ensure().write(
        'line_5\n'
        'line_3\n'
        'line_1\n',
    )
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.await_text('search(reverse-search)``:')
        h.press('line')
        h.await_text('search(reverse-search)`line`: line_1')
        h.press('^R')
        h.await_text('search(reverse-search)`line`: line_3')
        h.press('Enter')
        h.await_cursor_position(x=0, y=4)


def test_search_reverse_search_pos_during(run, xdg_data_home, ten_lines):
    xdg_data_home.join('babi/history/search').ensure().write(
        'line_3\n',
    )
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.press('ne')
        h.await_text('search(reverse-search)`ne`: line_3')
        h.await_cursor_position(y=23, x=30)
        h.press('^C')


def test_search_reverse_search_pos_after(run, xdg_data_home, ten_lines):
    xdg_data_home.join('babi/history/search').ensure().write(
        'line_3\n',
    )
    with run(str(ten_lines), height=20) as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.press('line')
        h.await_text('search(reverse-search)`line`: line_3')
        h.press('Right')
        h.await_text('search: line_3')
        h.await_cursor_position(y=19, x=14)
        h.press('^C')


def test_search_reverse_search_enter_appends(run, xdg_data_home, ten_lines):
    xdg_data_home.join('babi/history/search').ensure().write(
        'line_1\n'
        'line_3\n',
    )
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.press('1')
        h.await_text('search(reverse-search)`1`: line_1')
        h.press('Enter')
        h.press('^W')
        h.press('Up')
        h.await_text('search [line_1]: line_1')
        h.press('^C')


def test_search_reverse_search_history_cancel(run):
    with run() as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.await_text('search(reverse-search)``:')
        h.press('^C')
        h.await_text('cancelled')


def test_search_reverse_search_resizing(run):
    with run() as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        with h.resize(width=24, height=24):
            h.await_text('search(reverse-se…:')
            h.press('^C')


def test_search_reverse_search_does_not_wrap_around(run, xdg_data_home):
    xdg_data_home.join('babi/history/search').ensure().write(
        'line_1\n'
        'line_3\n',
    )
    with run() as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        # this should not wrap around
        for i in range(6):
            h.press('^R')
        h.await_text('search(reverse-search)``: line_1')
        h.press('^C')


def test_search_reverse_search_ctrl_r_on_failed_match(run, xdg_data_home):
    xdg_data_home.join('babi/history/search').ensure().write(
        'nomatch\n'
        'line_1\n',
    )
    with run() as h, and_exit(h):
        h.press('^W')
        h.press('^R')
        h.press('line')
        h.await_text('search(reverse-search)`line`: line_1')
        h.press('^R')
        h.await_text('search(failed reverse-search)`line`: line_1')
        h.press('^C')


def test_search_reverse_search_keeps_current_text_displayed(run):
    with run() as h, and_exit(h):
        h.press('^W')
        h.press('ohai')
        h.await_text('search: ohai')
        h.press('^R')
        h.await_text('search(reverse-search)``: ohai')
        h.press('^C')


def test_search_history_extra_blank_lines(run, xdg_data_home):
    with run() as h, and_exit(h):
        h.press('^W')
        h.press_and_enter('hello')
    with run() as h, and_exit(h):
        pass
    contents = xdg_data_home.join('babi/history/search').read()
    assert contents == 'hello\n'
