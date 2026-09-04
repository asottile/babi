from __future__ import annotations

import curses

from babi.buf import Buf
from babi.color_manager import ColorManager
from babi.highlight import Region
from babi.hl.interface import HL
from babi.hl.interface import HLs
from babi.hl.syntax import FileSyntax
from babi.theme import Theme


class BracketMatchHighlighter:
    include_edge = True

    def __init__(
        self,
        file_syntax: FileSyntax,
        theme: Theme,
        color_manager: ColorManager,
    ) -> None:
        self._file_syntax = file_syntax
        self._theme = theme
        self._color_manager = color_manager
        self._cache_cursor: tuple[int, int] | None = None
        self._cache_res: tuple[tuple[int, int], tuple[int, int]] | None = None
        # self.regions protocol support (list-like) needs to be careful
        self.regions = self

    def highlight_until(self, lines: Buf, idx: int) -> None:
        # Rely on FileSyntax being up to date
        pass

    def _find_matching(
        self,
        buf: Buf,
    ) -> tuple[str, int, int, str] | None:
        if not self._file_syntax._bracket_stacks:
            return None
        if not self._file_syntax._hl:
            return None

        cy, cx = buf.y, buf.x

        # Get stack state at start of current line
        if cy == 0:
            state = self._file_syntax._compiler.root_state
            stack: tuple[tuple[str, int, int], ...] = ()
        elif cy - 1 < len(self._file_syntax._bracket_stacks):
            stack = self._file_syntax._bracket_stacks[cy - 1]
            state = self._file_syntax._states[cy - 1]
        else:
            return None

        line = buf[cy]

        # Re-parse the current line to get exact regions
        regions: tuple[Region, ...]
        _, regions = self._file_syntax._hl(state, line, cy == 0)

        pairs = self._file_syntax.PAIRS
        open_chars = self._file_syntax.OPEN

        # Determine if we should include current char in stack
        target_x = cx
        if cx < len(line) and line[cx] in open_chars:
            target_x = cx + 1

        # Scan line logic
        current_stack = list(stack)

        for region in regions:
            is_non_code = False
            for s in region.scope:
                if any(
                    part in self._file_syntax.NON_CODE_SCOPES
                    for part in s.split('.')
                ):
                    is_non_code = True
                    break
            if is_non_code:
                continue

            # Check angular
            check_angular = any(
                target in region.scope
                for target in self._file_syntax.ANGULAR_SCOPES
            )

            text = line[region.start: region.end]

            for i, c in enumerate(text):
                abs_x = region.start + i
                if abs_x >= target_x:
                    break

                is_open = c in open_chars
                is_close = c in pairs
                if c == '<' and not check_angular:
                    is_open = False
                elif c == '>' and not check_angular:
                    is_close = False

                if is_open:
                    # push (char, y, x)
                    current_stack.append((c, cy, abs_x))
                elif is_close:
                    if current_stack:
                        if pairs[c] == current_stack[-1][0]:
                            current_stack.pop()
                        # For pessimisstic highlighting,
                        # unclosed remains on stack

            if region.end > target_x:
                break

        if not current_stack:
            return None

        open_char, open_y, open_x = current_stack[-1]

        target_close_char = None
        for k, v in pairs.items():
            if v == open_char:
                target_close_char = k
                break

        if target_close_char is None:
            return None

        return open_char, open_y, open_x, target_close_char

    def _get_bracket_pair(
        self,
        buf: Buf,
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return ((open_y, open_x), (close_y, close_x)) or None."""
        match = self._find_matching(buf)
        if match is None:
            return None

        open_char, open_y, open_x, target_close_char = match

        nesting = 0

        max_lines = len(buf)
        search_limit = 1000  # Avoid hanging on large files

        lines_checked = 0

        for y in range(open_y, max_lines):
            lines_checked += 1
            if lines_checked > search_limit:
                break

            if y >= len(self._file_syntax.regions):
                self._file_syntax.highlight_until(buf, y + 1)

            if y == 0:
                s_state = self._file_syntax._compiler.root_state
            else:
                if y - 1 >= len(self._file_syntax._states):
                    break
                s_state = self._file_syntax._states[y - 1]

            curr_line_text = buf[y]
            if self._file_syntax._hl is None:
                return None
            _, curr_line_regions = self._file_syntax._hl(
                s_state,
                curr_line_text,
                y == 0,
            )

            for region in curr_line_regions:
                # Check region start
                start_x = 0
                if y == open_y:
                    start_x = open_x + 1

                if region.end <= start_x and y == open_y:
                    continue

                is_non_code = False
                for s in region.scope:
                    if any(
                        part in self._file_syntax.NON_CODE_SCOPES
                        for part in s.split('.')
                    ):
                        is_non_code = True
                        break
                if is_non_code:
                    continue

                check_angular = any(
                    target in region.scope
                    for target in self._file_syntax.ANGULAR_SCOPES
                )

                chunk_text = curr_line_text[region.start: region.end]

                # Calculate start offset in chunk
                if y == open_y and region.start < start_x:
                    offset = start_x - region.start
                else:
                    offset = 0

                for i in range(offset, len(chunk_text)):
                    c = chunk_text[i]
                    is_open = c == open_char
                    is_close = c == target_close_char

                    if open_char == '<' and c in '<>':
                        if not check_angular:
                            is_open = False
                            is_close = False

                    if is_open:
                        nesting += 1
                    elif is_close:
                        if nesting > 0:
                            nesting -= 1
                        else:
                            final_x = region.start + i
                            return ((open_y, open_x), (y, final_x))

            # After first line, start_x is 0
            start_x = 0

        return None

    def __getitem__(self, idx: int) -> HLs:
        if not hasattr(self, 'buf'):
            return ()

        buf = self.buf
        if self._cache_cursor != (buf.y, buf.x):
            self._cache_cursor = (buf.y, buf.x)
            self._cache_res = self._get_bracket_pair(buf)

        if not self._cache_res:
            return ()

        (oy, ox), (cy, cx) = self._cache_res

        res = []
        style = self._theme.select(('match',))
        attr = style.attr(self._color_manager)
        if style == self._theme.default:
            attr = curses.A_BOLD | curses.A_REVERSE

        if idx == oy:
            res.append(HL(ox, ox + 1, attr))
        if idx == cy:
            res.append(HL(cx, cx + 1, attr))

        return tuple(res)

    def register_callbacks(self, buf: Buf) -> None:
        self.buf = buf

        # Invalidate cache on changes
        def clear_cache(*args: object) -> None:
            self._cache_cursor = None
            self._cache_res = None

        buf.add_set_callback(clear_cache)
        buf.add_del_callback(clear_cache)
        buf.add_ins_callback(clear_cache)
