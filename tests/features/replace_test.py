from __future__ import annotations

import pytest

from testing.runner import and_exit


@pytest.mark.parametrize('key', ('^C', 'Enter'))
def test_replace_cancel(run, key):
    with run() as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press(key)
        h.await_text('cancelled')


def test_replace_invalid_regex(run):
    with run() as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('(')
        h.await_text("invalid regex: '('")


def test_replace_invalid_replacement(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line_0')
        h.await_text('replace with:')
        h.press_and_enter('\\')
        h.await_text('invalid replacement string')


def test_replace_cancel_at_replace_string(run):
    with run() as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('hello')
        h.await_text('replace with:')
        h.press('^C')
        h.await_text('cancelled')


@pytest.mark.parametrize('key', ('y', 'Y'))
def test_replace_actual_contents(run, ten_lines, key):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line_0')
        h.await_text('replace with:')
        h.press_and_enter('ohai')
        h.await_text('replace [yes, no, all]?')
        h.press(key)
        h.await_text_missing('line_0')
        h.await_text('ohai')
        h.await_text(' *')
        h.await_text('replaced 1 occurrence')


def test_replace_sets_x_hint_properly(run, tmpdir):
    f = tmpdir.join('f')
    contents = '''\
beginning_line

match me!
'''
    f.write(contents)
    with run(str(f)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('me!')
        h.await_text('replace with:')
        h.press_and_enter('youuuu')
        h.await_text('replace [yes, no, all]?')
        h.press('y')
        h.await_cursor_position(x=6, y=3)
        h.press('Up')
        h.press('Up')
        h.await_cursor_position(x=6, y=1)


def test_replace_cancel_at_individual_replace(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter(r'line_\d')
        h.await_text('replace with:')
        h.press_and_enter('ohai')
        h.await_text('replace [yes, no, all]?')
        h.press('^C')
        h.await_text('cancelled')


def test_replace_unknown_characters_at_individual_replace(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter(r'line_\d')
        h.await_text('replace with:')
        h.press_and_enter('ohai')
        h.await_text('replace [yes, no, all]?')
        h.press('?')
        h.press('^C')
        h.await_text('cancelled')


def test_replace_say_no_to_individual_replace(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line_[135]')
        h.await_text('replace with:')
        h.press_and_enter('ohai')
        h.await_text('replace [yes, no, all]?')
        h.press('y')
        h.await_text_missing('line_1')
        h.press('n')
        h.await_text('line_3')
        h.press('y')
        h.await_text_missing('line_5')
        h.await_text('replaced 2 occurrences')


def test_replace_all(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter(r'line_(\d)')
        h.await_text('replace with:')
        h.press_and_enter(r'ohai+\1')
        h.await_text('replace [yes, no, all]?')
        h.press('a')
        h.await_text_missing('line')
        h.await_text('ohai+1')
        h.await_text('replaced 10 occurrences')


def test_replace_with_empty_string(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line_1')
        h.await_text('replace with:')
        h.press('Enter')
        h.await_text('replace [yes, no, all]?')
        h.press('y')
        h.await_text_missing('line_1')


def test_replace_search_not_found(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('wat')
        # TODO: would be nice to not prompt for a replace string in this case
        h.await_text('replace with:')
        h.press('Enter')
        h.await_text('no matches')


def test_replace_small_window_size(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line')
        h.await_text('replace with:')
        h.press_and_enter('wat')
        h.await_text('replace [yes, no, all]?')

        with h.resize(width=8, height=24):
            h.await_text('replace…')

        h.press('^C')


def test_replace_height_1_highlight(run, tmpdir):
    f = tmpdir.join('f')
    f.write('x' * 90)
    with run(str(f)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('^x+$')
        h.await_text('replace with:')
        h.press('Enter')
        h.await_text('replace [yes, no, all]?')

        with h.resize(width=80, height=1):
            h.await_text_missing('xxxxx')
        h.await_text('xxxxx')

        h.press('^C')


def test_replace_line_goes_off_screen(run):
    with run() as h, and_exit(h):
        h.press(f'{"a" * 20}{"b" * 90}')
        h.press('^A')
        h.await_text(f'{"a" * 20}{"b" * 59}»')
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('b+')
        h.await_text('replace with:')
        h.press_and_enter('wat')
        h.await_text('replace [yes, no, all]?')
        h.await_text(f'{"a" * 20}{"b" * 59}»')
        h.press('y')
        h.await_text(f'{"a" * 20}wat')
        h.await_text('replaced 1 occurrence')


def test_replace_undo_undoes_only_one(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line')
        h.await_text('replace with:')
        h.press_and_enter('wat')
        h.press('y')
        h.await_text_missing('line_0')
        h.press('y')
        h.await_text_missing('line_1')
        h.press('^C')
        h.press('M-u')
        h.await_text('line_1')
        h.await_text_missing('line_0')


def test_replace_multiple_occurrences_in_line(run):
    with run() as h, and_exit(h):
        h.press('baaaaabaaaaa')
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('a+')
        h.await_text('replace with:')
        h.press_and_enter('q')
        h.await_text('replace [yes, no, all]?')
        h.press('a')
        h.await_text('bqbq')


def test_replace_after_wrapping(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line_[02]')
        h.await_text('replace with:')
        h.press_and_enter('ohai')
        h.await_text('replace [yes, no, all]?')
        h.press('y')
        h.await_text_missing('line_2')
        h.press('y')
        h.await_text_missing('line_0')
        h.await_text('replaced 2 occurrences')


def test_replace_after_cursor_after_wrapping(run):
    with run() as h, and_exit(h):
        h.press('baaab')
        h.press('Left')
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('b')
        h.await_text('replace with:')
        h.press_and_enter('q')
        h.await_text('replace [yes, no, all]?')
        h.press('n')
        h.press('y')
        h.await_text('replaced 1 occurrence')
        h.await_text('qaaab')


def test_replace_separate_line_after_wrapping(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.press('Down')
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('line_[01]')
        h.await_text('replace with:')
        h.press_and_enter('_')
        h.await_text('replace [yes, no, all]?')
        h.press('y')
        h.await_text_missing('line_0')
        h.press('y')
        h.await_text_missing('line_1')


def test_replace_with_newline_characters(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('(line)_([01])')
        h.await_text('replace with:')
        h.press_and_enter(r'\1\n\2')
        h.await_text('replace [yes, no, all]?')
        h.press('a')
        h.await_text_missing('line_0')
        h.await_text_missing('line_1')
        h.await_text('line\n0\nline\n1\n')


def test_replace_with_multiple_newline_characters(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('(li)(ne)_(1)')
        h.await_text('replace with:')
        h.press_and_enter(r'\1\n\2\n\3\n')
        h.await_text('replace [yes, no, all]?')
        h.press('a')

        h.await_text_missing('line_1')
        h.await_text('li\nne\n1\n\nline_2')


def test_replace_end_of_file(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^\\')
        h.await_text('search (to replace):')
        h.press_and_enter('^')
        h.await_text('replace with:')
        h.press_and_enter('prefix:')
        h.await_text('replace [yes, no, all]?')
        h.press('a')

        h.await_text('replaced 10 occurrences')
        h.await_text('prefix:line_9')
        h.assert_screen_line_equal(11, '')
