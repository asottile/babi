import _curses
import argparse
import curses
from typing import Dict
from typing import Tuple


def _get_color_pair_mapping() -> Dict[Tuple[int, int], int]:
    ret = {}
    i = 0
    for bg in range(-1, 16):
        for fg in range(bg, 16):
            ret[(fg, bg)] = i
            i += 1
    return ret


COLORS = _get_color_pair_mapping()
del _get_color_pair_mapping


def _has_colors() -> bool:
    # https://github.com/python/typeshed/pull/3115
    return curses.has_colors and curses.COLORS >= 16  # type: ignore


def _color(fg: int, bg: int) -> int:
    if _has_colors():
        if bg > fg:
            return curses.A_REVERSE | curses.color_pair(COLORS[(bg, fg)])
        else:
            return curses.color_pair(COLORS[(fg, bg)])
    else:
        if bg > fg:
            return curses.A_REVERSE | curses.color_pair(0)
        else:
            return curses.color_pair(0)


def _init_colors(stdscr: '_curses._CursesWindow') -> None:
    curses.use_default_colors()
    if not _has_colors():
        return
    for (fg, bg), pair in COLORS.items():
        if pair == 0:  # cannot reset pair 0
            continue
        curses.init_pair(pair, fg, bg)


def _color_test(stdscr: '_curses._CursesWindow') -> None:
    maxy, maxx = stdscr.getmaxyx()
    if maxy < 16 or maxx < 64:
        raise SystemExit('--color-test needs a window of at least 64 x 16')

    x = y = 0
    for fg in range(-1, 16):
        for bg in range(-1, 16):
            if bg > fg:
                s = f'*{COLORS[bg, fg]:3}'
            else:
                s = f' {COLORS[fg, bg]:3}'
            stdscr.addstr(y, x, s, _color(fg, bg))
            x += 4
        y += 1
        x = 0


def c_main(stdscr: '_curses._CursesWindow', args: argparse.Namespace) -> None:
    _init_colors(stdscr)
    if args.color_test:
        _color_test(stdscr)
    stdscr.getch()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--color-test', action='store_true')
    args = parser.parse_args()
    curses.wrapper(c_main, args)
    return 0


if __name__ == '__main__':
    exit(main())
