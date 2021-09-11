from __future__ import annotations

from testing.runner import and_exit


def test_open_file_named_plus_something(run):
    with run('+3') as h, and_exit(h):
        h.await_text(' +3')


def test_initial_position_one_file(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello\nworld\n')

    with run('+2', str(f)) as h, and_exit(h):
        h.await_cursor_position(x=0, y=2)


def test_initial_position_multiple_files(run, tmpdir):
    f = tmpdir.join('f')
    f.write('1\n2\n3\n4\n')
    g = tmpdir.join('g')
    g.write('5\n6\n7\n8\n')

    with run('+2', str(f), '+3', str(g)) as h, and_exit(h):
        h.await_cursor_position(x=0, y=2)

        h.press('^X')

        h.await_cursor_position(x=0, y=3)
