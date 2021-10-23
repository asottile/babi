from __future__ import annotations

import argparse
from typing import Sequence

from babi.highlight import Compiler
from babi.highlight import Grammars
from babi.highlight import highlight_line
from babi.theme import Style
from babi.theme import Theme
from babi.user_data import prefix_data
from babi.user_data import xdg_config


def print_styled(s: str, style: Style) -> None:
    color_s = ''
    undo_s = ''
    if style.fg is not None:
        color_s += '\x1b[38;2;{r};{g};{b}m'.format(**style.fg._asdict())
        undo_s += '\x1b[39m'
    if style.bg is not None:
        color_s += '\x1b[48;2;{r};{g};{b}m'.format(**style.bg._asdict())
        undo_s += '\x1b[49m'
    if style.b:
        color_s += '\x1b[1m'
        undo_s += '\x1b[22m'
    if style.i:
        color_s += '\x1b[3m'
        undo_s += '\x1b[23m'
    if style.u:
        color_s += '\x1b[4m'
        undo_s += '\x1b[24m'
    print(f'{color_s}{s}{undo_s}', end='', flush=True)


def _highlight_output(theme: Theme, compiler: Compiler, filename: str) -> int:
    state = compiler.root_state

    if theme.default.bg is not None:
        print('\x1b[48;2;{r};{g};{b}m'.format(**theme.default.bg._asdict()))
    with open(filename, encoding='UTF-8') as f:
        for line_idx, line in enumerate(f):
            first_line = line_idx == 0
            state, regions = highlight_line(compiler, state, line, first_line)
            for start, end, scope in regions:
                print_styled(line[start:end], theme.select(scope))
    print('\x1b[m', end='')
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--theme', default=xdg_config('theme.json'))
    parser.add_argument('--grammar-dir', default=prefix_data('grammar_v1'))
    parser.add_argument('filename')
    args = parser.parse_args(argv)

    with open(args.filename, encoding='UTF-8') as f:
        first_line = next(f, '')

    theme = Theme.from_filename(args.theme)

    grammars = Grammars(args.grammar_dir)
    compiler = grammars.compiler_for_file(args.filename, first_line)

    return _highlight_output(theme, compiler, args.filename)


if __name__ == '__main__':
    raise SystemExit(main())
