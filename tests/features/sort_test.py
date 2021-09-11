from __future__ import annotations

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode


@pytest.fixture
def unsorted(tmpdir):
    f = tmpdir.join('f')
    f.write('d\nb\nc\na\n')
    return f


def test_sort_entire_file(run, unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'a\nb\nc\nd\n'


def test_reverse_sort_entire_file(run, unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':sort!')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'd\nc\nb\na\n'


def test_sort_selection(run, unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        h.press('S-Down')
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'b\nd\nc\na\n'


def test_reverse_sort_selection(run, unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        h.press('Down')
        h.press('S-Down')
        trigger_command_mode(h)
        h.press_and_enter(':sort!')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=2)
        h.press('^S')
    assert unsorted.read() == 'd\nc\nb\na\n'


def test_sort_selection_does_not_include_eof(run, unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        for _ in range(5):
            h.press('S-Down')
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'a\nb\nc\nd\n'


def test_sort_does_not_include_blank_line_after(run, tmpdir):
    f = tmpdir.join('f')
    f.write('b\na\n\nd\nc\n')

    with run(str(f)) as h, and_exit(h):
        h.press('S-Down')
        h.press('S-Down')
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert f.read() == 'a\nb\n\nd\nc\n'
