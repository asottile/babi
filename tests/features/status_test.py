from __future__ import annotations

from testing.runner import and_exit


def test_status_clearing_behaviour(run):
    with run() as h, and_exit(h):
        h.press('^J')
        h.await_text('unknown key')
        for i in range(24):
            h.press('Left')
        h.await_text('unknown key')
        h.press('Left')
        h.await_text_missing('unknown key')


def test_very_narrow_window_status(run):
    with run(height=50) as h, and_exit(h):
        with h.resize(width=5, height=50):
            h.press('^J')
            h.await_text('unkno')
