from __future__ import annotations

import curses

from babi.screen import VERSION_STR


def test_key_debug(run):
    with run('--key-debug') as h:
        h.await_text(VERSION_STR, timeout=2)

        h.await_text('press q to quit')

        h.press('a')
        h.await_text("'a' 'STRING'")

        h.press('^X')
        h.await_text(r"'\x18' '^X'")

        with h.resize(width=20, height=20):
            h.await_text(f"{curses.KEY_RESIZE} 'KEY_RESIZE'")

        h.press('q')
        h.await_exit()
