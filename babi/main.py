import argparse
import curses
import os
import sys
from typing import Optional
from typing import Sequence

from babi.file import File
from babi.perf import Perf
from babi.perf import perf_log
from babi.screen import EditResult
from babi.screen import make_stdscr
from babi.screen import Screen

CONSOLE = 'CONIN$' if sys.platform == 'win32' else '/dev/tty'


def _edit(screen: Screen, stdin: str) -> EditResult:
    screen.file.ensure_loaded(screen.status, stdin)

    while True:
        screen.status.tick(screen.margin)
        screen.draw()
        screen.file.move_cursor(screen.stdscr, screen.margin)

        key = screen.get_char()
        if key.keyname in File.DISPATCH:
            File.DISPATCH[key.keyname](screen.file, screen.margin)
        elif key.keyname in Screen.DISPATCH:
            ret = Screen.DISPATCH[key.keyname](screen)
            if isinstance(ret, EditResult):
                return ret
        elif key.keyname == b'STRING':
            assert isinstance(key.wch, str), key.wch
            screen.file.c(key.wch, screen.margin)
        else:
            screen.status.update(f'unknown key: {key}')


def c_main(
        stdscr: 'curses._CursesWindow',
        args: argparse.Namespace,
        stdin: str,
) -> int:
    with perf_log(args.perf_log) as perf:
        screen = Screen(stdscr, args.filenames or [None], perf)
        with screen.history.save():
            while screen.files:
                screen.i = screen.i % len(screen.files)
                res = _edit(screen, stdin)
                if res == EditResult.EXIT:
                    del screen.files[screen.i]
                    # always go to the next file except at the end
                    screen.i = min(screen.i, len(screen.files) - 1)
                    screen.status.clear()
                elif res == EditResult.NEXT:
                    screen.i += 1
                    screen.status.clear()
                elif res == EditResult.PREV:
                    screen.i -= 1
                    screen.status.clear()
                elif res == EditResult.OPEN:
                    screen.i = len(screen.files) - 1
                else:
                    raise AssertionError(f'unreachable {res}')
    return 0


def _key_debug(stdscr: 'curses._CursesWindow') -> int:
    screen = Screen(stdscr, ['<<key debug>>'], Perf())
    screen.file.lines = ['']

    while True:
        screen.status.update('press q to quit')
        screen.draw()
        screen.file.move_cursor(screen.stdscr, screen.margin)

        key = screen.get_char()
        screen.file.lines.insert(-1, f'{key.wch!r} {key.keyname.decode()!r}')
        screen.file.down(screen.margin)
        if key.wch == curses.KEY_RESIZE:
            screen.resize()
        if key.wch == 'q':
            return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', metavar='filename', nargs='*')
    parser.add_argument('--perf-log')
    parser.add_argument(
        '--key-debug', action='store_true', help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if '-' in args.filenames:
        print('reading stdin...', file=sys.stderr)
        stdin = sys.stdin.read()
        tty = os.open(CONSOLE, os.O_RDONLY)
        os.dup2(tty, sys.stdin.fileno())
    else:
        stdin = ''

    with make_stdscr() as stdscr:
        if args.key_debug:
            return _key_debug(stdscr)
        else:
            return c_main(stdscr, args, stdin)


if __name__ == '__main__':
    exit(main())
