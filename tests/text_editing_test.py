import pytest

from testing.runner import and_exit
from testing.runner import run


def test_basic_text_editing(tmpdir):
    with run() as h, and_exit(h):
        h.press('hello world')
        h.await_text('hello world')
        h.press('Down')
        h.press('bye!')
        h.await_text('bye!')
        assert h.screenshot().strip().endswith('world\nbye!')


def test_backspace_at_beginning_of_file():
    with run() as h, and_exit(h):
        h.press('BSpace')
        h.await_text_missing('unknown key')
        assert h.screenshot().strip().splitlines()[1:] == []
        assert '*' not in h.screenshot()


def test_backspace_joins_lines(tmpdir):
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


def test_backspace_at_end_of_file_still_allows_scrolling_down(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Down')
        h.press('BSpace')
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        assert '*' not in h.screenshot()


@pytest.mark.parametrize('key', ('BSpace', '^H'))
def test_backspace_deletes_text(tmpdir, key):
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


def test_delete_at_end_of_file(tmpdir):
    with run() as h, and_exit(h):
        h.press('DC')
        h.await_text_missing('unknown key')
        h.await_text_missing('*')


def test_delete_removes_character_afterwards(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Right')
        h.press('DC')
        h.await_text('hllo world')
        h.await_text('f *')


def test_delete_at_end_of_line(tmpdir):
    f = tmpdir.join('f')
    f.write('hello\nworld\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello')
        h.press('Down')
        h.press('Left')
        h.press('DC')
        h.await_text('helloworld')
        h.await_text('f *')


def test_press_enter_beginning_of_file(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Enter')
        h.await_text('\n\nhello world')
        h.await_cursor_position(x=0, y=2)
        h.await_text('f *')


def test_press_enter_mid_line(tmpdir):
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
