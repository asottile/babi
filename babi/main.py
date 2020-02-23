import argparse
import curses
from typing import Optional
from typing import Sequence

from babi.file import File
from babi.perf import perf_log
from babi.screen import EditResult
from babi.screen import make_stdscr
from babi.screen import Screen


def _edit(screen: Screen) -> EditResult:
    screen.file.ensure_loaded(screen.status)

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


def c_main(stdscr: 'curses._CursesWindow', args: argparse.Namespace) -> int:
    with perf_log(args.perf_log) as perf:
        screen = Screen(stdscr, args.filenames or [None], perf)
        with screen.history.save():
            while screen.files:
                screen.i = screen.i % len(screen.files)
                res = _edit(screen)
                if res == EditResult.EXIT:
                    del screen.files[screen.i]
                    screen.status.clear()
                elif res == EditResult.NEXT:
                    screen.i += 1
                    screen.status.clear()
                elif res == EditResult.PREV:
                    screen.i -= 1
                    screen.status.clear()
                else:
                    raise AssertionError(f'unreachable {res}')
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('filenames', metavar='filename', nargs='*')
    parser.add_argument('--perf-log')
    args = parser.parse_args(argv)

    with make_stdscr() as stdscr:
        return c_main(stdscr, args)


if __name__ == '__main__':
    exit(main())
