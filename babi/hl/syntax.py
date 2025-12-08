from __future__ import annotations

import curses
import functools
import math
from collections.abc import Callable
from typing import cast
from typing import NamedTuple

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.highlight import Compiler
from babi.highlight import Grammars
from babi.highlight import highlight_line
from babi.highlight import Region
from babi.highlight import State
from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.theme import PartialStyle
from babi.theme import Style
from babi.theme import Theme
from babi.user_data import prefix_data
from babi.user_data import xdg_config
from babi.user_data import xdg_data


BracketStack = tuple[str, ...]


# TODO: make this configurable?
def _make_color(s: str) -> dict[str, str]:
    return {'foreground': s}


RAINBOW_COLORS = (
    PartialStyle.from_dct(_make_color('#ffd700')),  # gold
    PartialStyle.from_dct(_make_color('#da70d6')),  # orchid
    PartialStyle.from_dct(_make_color('#179fff')),  # light sky blue
)
OPEN = '([{'
CLOSE = ')]}'
# Bit of a hack, but we need to know if a region is a string or
# comment to avoid highlighting brackets inside them. This is my best effort
# check based on the scope name.
NON_CODE_SCOPES = {'string', 'comment'}


class FileSyntax:
    include_edge = False

    def __init__(
        self,
        compiler: Compiler,
        theme: Theme,
        color_manager: ColorManager,
    ) -> None:
        self._compiler = compiler
        self._theme = theme
        self._color_manager = color_manager

        self.regions: list[HLs] = []
        self._states: list[State] = []
        self._bracket_stacks: list[BracketStack] = []

        # this will be assigned a functools.lru_cache per instance for
        # better hit rate and memory usage
        self._hl: Callable[[State, str, bool], tuple[State, HLs]] | None
        self._hl = None

    @property
    def root_scope(self) -> str:
        return self._compiler.root_scope

    NON_CODE_SCOPES = {'string', 'comment'}
    ANGULAR_SCOPES = {  # only treat <> as brackets if syntax scope makes sense
        'punctuation.definition.tag',
        'punctuation.definition.generic',
        'punctuation.definition.typeparameters',
    }
    PAIRS = {')': '(', ']': '[', '}': '{', '>': '<'}
    OPEN = set(PAIRS.values())

    def _hl_uncached(
        self,
        state: State,
        line: str,
        first_line: bool,
    ) -> tuple[State, tuple[Region, ...]]:
        new_state, regions = highlight_line(
            self._compiler,
            state,
            f"{line}\n",
            first_line=first_line,
        )

        # remove the trailing newline
        new_end = regions[-1]._replace(end=regions[-1].end - 1)
        regions = regions[:-1] + (new_end,)
        return new_state, regions

    def _render_line(
        self,
        regions: tuple[Region, ...],
        line: str,
        stack: BracketStack,
    ) -> tuple[HLs, BracketStack]:
        regs: list[HL] = []
        for r in regions:
            style = self._theme.select(r.scope)
            # skip if default but continue if we need to search for brackets

            attr = style.attr(self._color_manager)

            if style != self._theme.default:
                if regs and regs[-1].attr == attr and regs[-1].end == r.start:
                    regs[-1] = regs[-1]._replace(end=r.end)
                else:
                    regs.append(HL(x=r.start, end=r.end, attr=attr))

            # if any part of the scope is a string or comment, skip rainbow
            if any(
                part in self.NON_CODE_SCOPES for s in r.scope
                for part in s.split('.')
            ):
                continue

            # check if we should look for angular brackets in this region
            check_angular = any(
                target in s for s in r.scope for target in self.ANGULAR_SCOPES
            )

            last = r.start
            text = line[r.start: r.end]
            for i, c in enumerate(text):
                is_open = c in self.OPEN
                is_close = c in self.PAIRS

                if c == '<':
                    if not check_angular:
                        is_open = False
                elif c == '>':
                    if not check_angular:
                        is_close = False

                if is_open:
                    idx = r.start + i
                    if idx > last:
                        regs.append(HL(last, idx, attr))

                    if self._theme.rainbow_colors:
                        rainbow_colors = self._theme.rainbow_colors
                    else:
                        rainbow_colors = RAINBOW_COLORS

                    color_idx = len(stack) % len(rainbow_colors)
                    brace_style = style._asdict()
                    rainbow_colors[color_idx].overlay_on(brace_style)
                    brace_attr = Style(**brace_style).attr(self._color_manager)

                    regs.append(HL(idx, idx + 1, brace_attr))
                    stack = stack + (c,)
                    last = idx + 1
                elif is_close:
                    # pop if match
                    curr_open = self.PAIRS[c]
                    if stack and stack[-1] == curr_open:
                        stack = stack[:-1]

                    idx = r.start + i
                    if idx > last:
                        regs.append(HL(last, idx, attr))

                    if self._theme.rainbow_colors:
                        rainbow_colors = self._theme.rainbow_colors
                    else:
                        rainbow_colors = RAINBOW_COLORS

                    color_idx = len(stack) % len(rainbow_colors)
                    brace_style = style._asdict()
                    rainbow_colors[color_idx].overlay_on(brace_style)
                    brace_attr = Style(**brace_style).attr(self._color_manager)

                    regs.append(HL(idx, idx + 1, brace_attr))
                    last = idx + 1

        return tuple(regs), stack

    def _set_cb(self, lines: Buf, idx: int, victim: str) -> None:
        del self.regions[idx:]
        del self._states[idx:]
        del self._bracket_stacks[idx:]

    def _del_cb(self, lines: Buf, idx: int, victim: str) -> None:
        del self.regions[idx:]
        del self._states[idx:]
        del self._bracket_stacks[idx:]

    def _ins_cb(self, lines: Buf, idx: int) -> None:
        del self.regions[idx:]
        del self._states[idx:]
        del self._bracket_stacks[idx:]

    def register_callbacks(self, buf: Buf) -> None:
        buf.add_set_callback(self._set_cb)
        buf.add_del_callback(self._del_cb)
        buf.add_ins_callback(self._ins_cb)

    def highlight_until(self, lines: Buf, idx: int) -> None:
        if self._hl is None:
            # the docs claim better performance with power of two sizing
            size = max(4096, 2 ** (int(math.log(len(lines), 2)) + 2))
            self._hl = functools.lru_cache(maxsize=size)(self._hl_uncached)

        if not self._states:
            state = self._compiler.root_state
            stack: BracketStack = ()
        else:
            state = self._states[-1]
            stack = self._bracket_stacks[-1]

        for i in range(len(self._states), idx):
            ret = self._hl(state, lines[i], i == 0)
            state, line_regions = cast('tuple[State, tuple[Region, ...]]', ret)
            hls, stack = self._render_line(line_regions, lines[i], stack)
            self._states.append(state)
            self.regions.append(hls)
            self._bracket_stacks.append(stack)


class Syntax(NamedTuple):
    grammars: Grammars
    theme: Theme
    color_manager: ColorManager

    def file_highlighter(self, filename: str, first_line: str) -> FileSyntax:
        compiler = self.grammars.compiler_for_file(filename, first_line)
        return FileSyntax(compiler, self.theme, self.color_manager)

    def blank_file_highlighter(self) -> FileSyntax:
        compiler = self.grammars.blank_compiler()
        return FileSyntax(compiler, self.theme, self.color_manager)

    def _init_screen(self, stdscr: curses.window) -> None:
        default_fg, default_bg = self.theme.default.fg, self.theme.default.bg
        all_colors = {c for c in (default_fg, default_bg) if c is not None}
        todo = list(self.theme.rules.children.values())
        while todo:
            rule = todo.pop()
            if rule.style.fg is not None:
                all_colors.add(rule.style.fg)
            if rule.style.bg is not None:
                all_colors.add(rule.style.bg)
            todo.extend(rule.children.values())

        for style in self.theme.rainbow_colors or RAINBOW_COLORS:
            if style.fg is not None:
                all_colors.add(style.fg)

        for color in sorted(all_colors):
            self.color_manager.init_color(color)

        pair = self.color_manager.color_pair(default_fg, default_bg)
        stdscr.bkgd(' ', curses.color_pair(pair))

    @classmethod
    def from_screen(
        cls,
        stdscr: curses.window,
        color_manager: ColorManager,
    ) -> Syntax:
        grammars = Grammars(prefix_data('grammar_v1'), xdg_data('grammar_v1'))
        theme = Theme.from_filename(xdg_config('theme.json'))
        ret = cls(grammars, theme, color_manager)
        ret._init_screen(stdscr)
        return ret
