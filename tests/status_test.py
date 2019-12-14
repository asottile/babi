from testing.runner import and_exit
from testing.runner import run


def test_status_clearing_behaviour():
    with run() as h, and_exit(h):
        h.press('^J')
        h.await_text('unknown key')
        for i in range(24):
            h.press('LEFT')
        h.await_text('unknown key')
        h.press('LEFT')
        h.await_text_missing('unknown key')


def test_very_narrow_window_status():
    with run(height=50) as h, and_exit(h):
        with h.resize(5, 50):
            h.press('^J')
            h.await_text('unkno')
