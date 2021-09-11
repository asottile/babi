from __future__ import annotations

from testing.runner import and_exit


def test_open_cancelled(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        h.press('^P')
        h.await_text('enter filename:')
        h.press('^C')

        h.await_text('cancelled')
        h.await_text('hello world')


def test_open(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')
    g = tmpdir.join('g')
    g.write('goodbye world')

    with run(str(f)) as h:
        h.await_text('hello world')

        h.press('^P')
        h.press_and_enter(str(g))

        h.await_text('[2/2]')
        h.await_text('goodbye world')

        h.press('^X')
        h.await_text('hello world')

        h.press('^X')
        h.await_exit()
