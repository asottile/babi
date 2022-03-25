from __future__ import annotations

import pytest

from testing.runner import and_exit


def test_basic_text_editing(run, tmpdir):
    with run() as h, and_exit(h):
        h.press('hello world')
        h.await_text('hello world')
        h.press('Down')
        h.press('bye!')
        h.await_text('bye!')
        h.await_text('hello world\nbye!\n')


def test_backspace_at_beginning_of_file(run):
    with run() as h, and_exit(h):
        h.press('BSpace')
        h.await_text_missing('unknown key')
        h.assert_cursor_line_equal('')
        h.await_text_missing('*')


def test_backspace_joins_lines(run, tmpdir):
    f = tmpdir.join('f')
    f.write('foo\nbar\nbaz\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('foo')
        h.press('Down')
        h.press('BSpace')
        h.await_text('foobar')
        h.await_text('f *')
        h.await_cursor_position(x=3, y=1)
        # pressing down should retain the X position
        h.press('Down')
        h.await_cursor_position(x=3, y=2)


def test_backspace_at_end_of_file_still_allows_scrolling_down(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Down')
        h.press('BSpace')
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.await_text_missing('*')


def test_backspace_deletes_newline_at_end_of_file(run, tmpdir):
    f = tmpdir.join('f')
    f.write('foo\n\n')

    with run(str(f)) as h, and_exit(h):
        h.press('^End')
        h.press('BSpace')
        h.press('^S')

    assert f.read() == 'foo\n'


@pytest.mark.parametrize('key', ('BSpace', '^H'))
def test_backspace_deletes_text(run, tmpdir, key):
    f = tmpdir.join('f')
    f.write('ohai there')

    with run(str(f)) as h, and_exit(h):
        h.await_text('ohai there')
        for _ in range(3):
            h.press('Right')
        h.press(key)
        h.await_text('ohi')
        h.await_text('f *')
        h.await_cursor_position(x=2, y=1)


def test_delete_at_end_of_file(run, tmpdir):
    with run() as h, and_exit(h):
        h.press('DC')
        h.await_text_missing('unknown key')
        h.await_text_missing('*')


@pytest.mark.parametrize('key', ('DC', '^D'))
def test_delete_removes_character_afterwards(run, tmpdir, key):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Right')
        h.press(key)
        h.await_text('hllo world')
        h.await_text('f *')


def test_delete_at_end_of_line(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello\nworld\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello')
        h.press('Down')
        h.press('Left')
        h.press('DC')
        h.await_text('helloworld')
        h.await_text('f *')


def test_delete_at_end_of_last_line(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello')
        h.press('End')
        h.press('DC')
        # should not make the file modified
        h.await_text_missing('*')

        # delete should still be functional
        h.press('Left')
        h.press('Left')
        h.press('DC')
        h.await_text('helo')


def test_press_enter_beginning_of_file(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Enter')
        h.await_text('\n\nhello world')
        h.await_cursor_position(x=0, y=2)
        h.await_text('f *')


def test_press_enter_mid_line(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        for _ in range(5):
            h.press('Right')
        h.press('Enter')
        h.await_text('hello\n world')
        h.await_cursor_position(x=0, y=2)
        h.press('Up')
        h.await_cursor_position(x=0, y=1)


def test_press_string_sequence(run):
    with run() as h, and_exit(h):
        h.press('hello world\x1bOH')
        h.await_text('hello world')
        h.await_cursor_position(x=0, y=1)
