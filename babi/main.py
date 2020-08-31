import argparse
import curses
import os
import re
import signal
import sys
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

from babi.buf import Buf
from babi.file import File
from babi.perf import Perf
from babi.perf import perf_log
from babi.screen import EditResult
from babi.screen import make_stdscr
from babi.screen import Screen

CONSOLE = 'CONIN$' if sys.platform == 'win32' else '/dev/tty'
POSITION_RE = re.compile(r'^\+-?\d+$')


def _edit(screen: Screen, stdin: str) -> EditResult:
    screen.file.ensure_loaded(screen.status, screen.margin, stdin)

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
        filenames: List[Optional[str]],
        positions: List[int],
        stdin: str,
        perf: Perf,
) -> int:
    screen = Screen(stdscr, filenames, positions, perf)
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


def _key_debug(stdscr: 'curses._CursesWindow', perf: Perf) -> int:
    screen = Screen(stdscr, ['<<key debug>>'], [0], perf)
    screen.file.buf = Buf([''])

    while True:
        screen.status.update('press q to quit')
        screen.draw()
        screen.file.move_cursor(screen.stdscr, screen.margin)

        key = screen.get_char()
        screen.file.buf.insert(-1, f'{key.wch!r} {key.keyname.decode()!r}')
        screen.file.down(screen.margin)
        if key.wch == curses.KEY_RESIZE:
            screen.resize()
        if key.wch == 'q':
            return 0


def _filenames(filenames: List[str]) -> Tuple[List[Optional[str]], List[int]]:
    if not filenames:
        return [None], [0]

    ret_filenames: List[Optional[str]] = []
    ret_positions = []

    filenames_iter = iter(filenames)
    for filename in filenames_iter:
        if POSITION_RE.match(filename):
            # in the success case we get:
            #
            # position_s = +...
            # filename = (the next thing)
            #
            # in the error case we only need to reset `position_s` as
            # `filename` is already correct
            position_s = filename
            try:
                filename = next(filenames_iter)
            except StopIteration:
                position_s = '+0'
            ret_positions.append(int(position_s[1:]))
            ret_filenames.append(filename)
        else:
            ret_positions.append(0)
            ret_filenames.append(filename)

    return ret_filenames, ret_positions


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
        stdin = sys.stdin.buffer.read().decode()
        tty = os.open(CONSOLE, os.O_RDONLY)
        os.dup2(tty, sys.stdin.fileno())
    else:
        stdin = ''

    # ignore backgrounding signals, we'll handle those in curses
    # fixes a problem with ^Z on termination which would break the terminal
    if sys.platform != 'win32':  # pragma: win32 no cover  # pragma: no branch
        signal.signal(signal.SIGTSTP, signal.SIG_IGN)

    with perf_log(args.perf_log) as perf, make_stdscr() as stdscr:
        if args.key_debug:
            return _key_debug(stdscr, perf)
        else:
            filenames, positions = _filenames(args.filenames)
            return c_main(stdscr, filenames, positions, stdin, perf)


if __name__ == '__main__':
    exit(main())
