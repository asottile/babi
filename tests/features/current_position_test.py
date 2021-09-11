from __future__ import annotations

from testing.runner import and_exit


def test_current_position(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^C')
        h.await_text('line 1, col 1 (of 10 lines)')
        h.press('Right')
        h.press('^C')
        h.await_text('line 1, col 2 (of 10 lines)')
        h.press('Down')
        h.press('^C')
        h.await_text('line 2, col 2 (of 10 lines)')
        h.press('Up')
        for i in range(10):
            h.press('^K')
        h.press('^C')
        h.await_text('line 1, col 1 (of 1 line)')
