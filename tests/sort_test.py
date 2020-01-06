import pytest

from testing.runner import and_exit
from testing.runner import run
from testing.runner import trigger_command_mode


@pytest.fixture
def unsorted(tmpdir):
    f = tmpdir.join('f')
    f.write('d\nb\nc\na\n')
    return f


def test_sort_entire_file(unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'a\nb\nc\nd\n'


def test_sort_selection(unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        h.press('S-Down')
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'b\nd\nc\na\n'


def test_sort_selection_does_not_include_eof(unsorted):
    with run(str(unsorted)) as h, and_exit(h):
        for _ in range(5):
            h.press('S-Down')
        trigger_command_mode(h)
        h.press_and_enter(':sort')
        h.await_text('sorted!')
        h.await_cursor_position(x=0, y=1)
        h.press('^S')
    assert unsorted.read() == 'a\nb\nc\nd\n'
