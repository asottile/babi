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
from babi.theme import Theme
from babi.user_data import prefix_data
from babi.user_data import xdg_config
from babi.user_data import xdg_data


BracketStack = tuple[tuple[str, int, int], ...]


# TODO: make this configurable?
def _make_color(s: str) -> dict[str, str]:
    return {'foreground': s}


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
        self._bracket_stacks: list[tuple[tuple[str, int, int], ...]] = []

        # this will be assigned a functools.lru_cache per instance for
        # better hit rate and memory usage
        self._hl: (
            Callable[
                [State, str, bool],
                tuple[State, tuple[Region, ...]],
            ] |
            None
        )
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
        stack: tuple[tuple[str, int, int], ...],
        line_idx: int,
    ) -> tuple[HLs, tuple[tuple[str, int, int], ...]]:
        regs: list[HL] = []
        for r in regions:
            # Base highlighting
            style = self._theme.select(r.scope)
            attr = style.attr(self._color_manager)
            # OPTIMIZATION: merge with previous if same attr and contiguous
            if style != self._theme.default:
                if regs and regs[-1].attr == attr and regs[-1].end == r.start:
                    regs[-1] = regs[-1]._replace(end=r.end)
                else:
                    regs.append(HL(x=r.start, end=r.end, attr=attr))

            # if any part of the scope is a string or comment, skip rainbow
            if any(
                part in self.NON_CODE_SCOPES
                for s in r.scope
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

                    # Pessimistic: Start INVALID
                    brace_attr = self._get_invalid_attr()

                    regs.append(HL(idx, idx + 1, brace_attr))
                    stack = stack + ((c, line_idx, idx),)
                    last = idx + 1
                elif is_close:
                    idx = r.start + i
                    # pop if match
                    curr_open = self.PAIRS[c]
                    if stack and stack[-1][0] == curr_open:
                        # MATCH FOUND!
                        # 1. Update the OPEN bracket (popped) to be VALID
                        open_char, open_y, open_x_val = stack[-1]

                        valid_attr = self._get_valid_attr(r.scope)

                        if open_y == line_idx:
                            # Update in current regs list
                            # Iterate BACKWARDS to find bracket HL
                            for k in range(len(regs) - 1, -1, -1):
                                if regs[k].x == open_x_val:
                                    regs[k] = regs[k]._replace(
                                        attr=valid_attr,
                                    )
                                    break
                        else:
                            # Update in committed regions
                            self._update_region_attr(
                                open_y,
                                open_x_val,
                                valid_attr,
                            )

                        stack = stack[:-1]

                        if idx > last:
                            regs.append(HL(last, idx, attr))

                        # 2. Render current CLOSE bracket as VALID
                        valid_attr = self._get_valid_attr(r.scope)
                        regs.append(HL(idx, idx + 1, valid_attr))
                        last = idx + 1
                    else:
                        # Mismatched bracket
                        if idx > last:
                            regs.append(HL(last, idx, attr))

                        brace_attr = self._get_invalid_attr()
                        regs.append(HL(idx, idx + 1, brace_attr))
                        last = idx + 1

        return tuple(regs), stack

    def _update_region_attr(self, y: int, x: int, attr: int) -> None:
        if y >= len(self.regions):
            return

        # We need to find the HL at x.
        # Regions for line y is a tuple of HLs.
        # Iterate BACKWARDS to find the bracket HL (appended LAST)
        hls = list(self.regions[y])
        for i in range(len(hls) - 1, -1, -1):
            if hls[i].x == x:
                hls[i] = hls[i]._replace(attr=attr)
                self.regions[y] = tuple(hls)
                return

    def _get_invalid_attr(self) -> int:
        # Fallback for invalid brackets: Invalid style (Red) or BOLD|REVERSE
        # We can try to get explicit 'invalid' scope style from the theme
        invalid_style = self._theme.select(('invalid',))
        attr = invalid_style.attr(self._color_manager)
        if attr == 0:
            # If theme has no invalid style, force BOLD + REVERSE as fallback?
            # Or just BOLD?
            # If logic requires specific invalid style, we should ensure it.
            # BOLD alone is subtle. REVERSE is strong.
            return curses.A_BOLD | curses.A_REVERSE
        # If theme provides non-zero invalid style (e.g. fg color), ensure BOLD
        return attr | curses.A_BOLD

    def _get_valid_attr(self, scope: tuple[str, ...]) -> int:
        style = self._theme.select(scope)
        return style.attr(self._color_manager) | curses.A_BOLD

    def _reset_stack_attrs(self, idx: int) -> None:
        if idx > 0 and idx - 1 < len(self._bracket_stacks):
            stack = self._bracket_stacks[idx - 1]
            invalid_attr = self._get_invalid_attr()
            for item in stack:
                # item is (char, y, x)
                self._update_region_attr(item[1], item[2], invalid_attr)

    def _set_cb(self, lines: Buf, idx: int, victim: str) -> None:
        self._reset_stack_attrs(idx)
        del self.regions[idx:]
        del self._states[idx:]
        del self._bracket_stacks[idx:]

    def _del_cb(self, lines: Buf, idx: int, victim: str) -> None:
        self._reset_stack_attrs(idx)
        del self.regions[idx:]
        del self._states[idx:]
        del self._bracket_stacks[idx:]

    def _ins_cb(self, lines: Buf, idx: int) -> None:
        # idx is the line of insertion.
        # If we insert at idx, it means lines BEFORE idx are valid.
        # But wait, inserting a newline splits a line?
        # Buf callbacks:
        # ins: insert new line at idx.
        # The stack state flowing INTO idx comes from idx-1.
        self._reset_stack_attrs(idx)
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
            if i >= len(lines):
                break
            ret = self._hl(state, lines[i], i == 0)
            state, line_regions = cast('tuple[State, tuple[Region, ...]]', ret)
            hls, stack = self._render_line(line_regions, lines[i], stack, i)
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
