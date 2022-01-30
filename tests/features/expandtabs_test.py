from __future__ import annotations

from testing.runner import and_exit
from testing.runner import trigger_command_mode


def test_set_expandtabs(run, tmpdir):
    f = tmpdir.join('f')
    f.write('a')

    with run(str(f)) as h, and_exit(h):
        h.press('Left')
        trigger_command_mode(h)
        h.press_and_enter(':expandtabs')
        h.await_text('updated!')
        h.press('Tab')
        h.press('^S')
    assert f.read() == '    a\n'


def test_set_noexpandtabs(run, tmpdir):
    f = tmpdir.join('f')
    f.write('a')

    with run(str(f)) as h, and_exit(h):
        h.press('Left')
        trigger_command_mode(h)
        h.press_and_enter(':noexpandtabs')
        h.await_text('updated!')
        h.press('Tab')
        h.press('^S')
    assert f.read() == '\ta\n'


def test_indent_with_expandtabs(run, tmpdir):
    f = tmpdir.join('f')
    f.write('a\nb\nc')

    with run(str(f)) as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':noexpandtabs')
        h.await_text('updated!')
        for _ in range(3):
            h.press('S-Down')
        h.press('Tab')
        h.press('^S')
    assert f.read() == '\ta\n\tb\n\tc\n'


def test_expandtabs_incorrect_number_of_arguments(run):
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':expandtabs 1')
        h.await_text('`:expandtabs`: expected 0 args but got 1')
