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


def test_file_glob(run, tmpdir):
    base = 'globtest'
    prefix = base + 'ffff.txt'
    f = tmpdir.join(prefix + 'f')
    f.write('hello world')
    g = tmpdir.join(base + 'fggg')
    g.write('goodbye world')
    nonexistant = str(tmpdir.join('NONEXISTANT'))

    with run(str(g)) as h:
        h.await_text('goodbye world')

        h.press('^P')
        h.press(nonexistant)
        h.press('Tab')
        h.await_text(f'«{nonexistant[-7:]}')
        h.press('^C')
        h.await_text('cancelled')
        h.press('^P')
        h.press(str(tmpdir.join(base + 'fff')))
        h.press('Tab')
        h.await_text(str(f)[-7:])
        h.press('Tab')  # second tab shouldn't change anything
        h.await_text(str(f)[-7:])
        h.press('Enter')
        h.await_text('[2/2]')
        h.await_text('hello world')
        h.press('^X')
        h.press('^X')
        h.await_exit()
