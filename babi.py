import _curses
import argparse
import curses
from typing import Dict
from typing import Tuple

VERSION_STR = 'babi v0'


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
    stdscr.get_wch()


def _write_header(
        stdscr: '_curses._CursesWindow',
        filename: str,
        *,
        modified: bool,
) -> None:
    filename = filename or '<<new file>>'
    if modified:
        filename += ' *'
    centered_filename = filename.center(curses.COLS)[len(VERSION_STR) + 2:]
    s = f' {VERSION_STR} {centered_filename}'
    stdscr.addstr(0, 0, s, curses.A_REVERSE)


def _write_status(stdscr: '_curses._CursesWindow', status: str) -> None:
    stdscr.addstr(curses.LINES - 1, 0, ' ' * (curses.COLS - 1))
    if status:
        status = f' {status} '
        offset = (curses.COLS - len(status)) // 2
        stdscr.addstr(curses.LINES - 1, offset, status, curses.A_REVERSE)


def c_main(stdscr: '_curses._CursesWindow', args: argparse.Namespace) -> None:
    _init_colors(stdscr)

    if args.color_test:
        return _color_test(stdscr)

    filename = args.filename
    status = ''
    status_action_counter = -1
    position_y, position_x = 0, 0

    def _set_status(s: str) -> None:
        nonlocal status, status_action_counter
        status = s
        status_action_counter = 25

    while True:
        if status_action_counter == 0:
            status = ''
        status_action_counter -= 1

        _write_header(stdscr, filename, modified=False)
        _write_status(stdscr, status)
        stdscr.move(position_y + 1, position_x)

        wch = stdscr.get_wch()
        key = wch if isinstance(wch, int) else ord(wch)
        keyname = curses.keyname(key)

        if key == curses.KEY_RESIZE:
            curses.update_lines_cols()
        elif key == curses.KEY_DOWN:
            position_y = min(position_y + 1, curses.LINES - 2)
        elif key == curses.KEY_UP:
            position_y = max(position_y - 1, 0)
        elif key == curses.KEY_RIGHT:
            position_x = min(position_x + 1, curses.COLS - 1)
        elif key == curses.KEY_LEFT:
            position_x = max(position_x - 1, 0)
        elif keyname == b'^X':
            return
        else:
            _set_status(f'unknown key: {keyname} ({key})')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--color-test', action='store_true')
    parser.add_argument('filename', nargs='?')
    args = parser.parse_args()
    curses.wrapper(c_main, args)
    return 0


if __name__ == '__main__':
    exit(main())
