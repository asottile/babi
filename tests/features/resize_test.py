from __future__ import annotations

from babi.screen import VERSION_STR
from testing.runner import and_exit


def test_window_height_2(run, tmpdir):
    # 2 tall:
    # - header is hidden, otherwise behaviour is normal
    f = tmpdir.join('f.txt')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        with h.resize(width=80, height=2):
            h.await_text_missing(VERSION_STR)
            h.assert_full_contents('hello world\n\n')
            h.press('^J')
            h.await_text('unknown key')

        h.await_text(VERSION_STR)


def test_window_height_1(run, tmpdir):
    # 1 tall:
    # - only file contents as body
    # - status takes precedence over body, but cleared after single action
    f = tmpdir.join('f.txt')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        with h.resize(width=80, height=1):
            h.await_text_missing(VERSION_STR)
            h.assert_full_contents('hello world\n')
            h.press('^J')
            h.await_text('unknown key')
            h.press('Right')
            h.await_text_missing('unknown key')
            h.press('Down')


def test_reacts_to_resize(run):
    with run() as h, and_exit(h):
        h.await_text('<<new file>>')
        with h.resize(width=10, height=20):
            h.await_text_missing('<<new file>>')
        h.await_text('<<new file>>')


def test_resize_scrolls_up(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.await_text('line_9')

        for _ in range(7):
            h.press('Down')
        h.await_cursor_position(x=0, y=8)

        # a resize to a height of 10 should not scroll
        with h.resize(width=80, height=10):
            h.await_text_missing('line_8')
            h.await_cursor_position(x=0, y=8)

        h.await_text('line_8')

        # but a resize to smaller should
        with h.resize(width=80, height=9):
            h.await_text_missing('line_0')
            h.await_cursor_position(x=0, y=4)
            # make sure we're still on the same line
            h.assert_cursor_line_equal('line_7')


def test_resize_scroll_does_not_go_negative(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        for _ in range(5):
            h.press('Down')
        h.await_cursor_position(x=0, y=6)

        with h.resize(width=80, height=7):
            h.await_text_missing('line_9')
        h.await_text('line_9')

        for _ in range(3):
            h.press('Up')

        h.assert_screen_line_equal(1, 'line_0')


def test_horizontal_scrolling(run, tmpdir):
    f = tmpdir.join('f')
    lots_of_text = ''.join(
        ''.join(str(i) * 10 for i in range(10))
        for _ in range(10)
    )
    f.write(f'line1\n{lots_of_text}\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('6777777777»')
        h.press('Down')
        for _ in range(78):
            h.press('Right')
        h.await_text('6777777777»')
        h.press('Right')
        h.await_text('«77777778')
        h.await_text('344444444445»')
        h.await_cursor_position(x=7, y=2)
        for _ in range(71):
            h.press('Right')
        h.await_text('«77777778')
        h.await_text('344444444445»')
        h.press('Right')
        h.await_text('«444445')
        h.await_text('1222»')


def test_horizontal_scrolling_exact_width(run, tmpdir):
    f = tmpdir.join('f')
    f.write('0' * 80)

    with run(str(f)) as h, and_exit(h):
        h.await_text('000')
        for _ in range(78):
            h.press('Right')
        h.await_text_missing('»')
        h.await_cursor_position(x=78, y=1)
        h.press('Right')
        h.await_text('«0000000')
        h.await_cursor_position(x=7, y=1)


def test_horizontal_scrolling_narrow_window(run, tmpdir):
    f = tmpdir.join('f')
    f.write(''.join(str(i) * 10 for i in range(10)))

    with run(str(f)) as h, and_exit(h):
        with h.resize(width=5, height=24):
            h.await_text('0000»')
            for _ in range(3):
                h.press('Right')
            h.await_text('0000»')
            h.press('Right')
            h.await_cursor_position(x=3, y=1)
            h.await_text('«000»')
            for _ in range(6):
                h.press('Right')
            h.await_text('«001»')


def test_window_width_1(run, tmpdir):
    f = tmpdir.join('f')
    f.write('hello')

    with run(str(f)) as h, and_exit(h):
        with h.resize(width=1, height=24):
            h.await_text('»')
            for _ in range(3):
                h.press('Right')
        h.await_text('hello')
        h.await_cursor_position(x=3, y=1)


def test_resize_while_cursor_at_bottom(run, tmpdir):
    f = tmpdir.join('f')
    f.write('x\n' * 35)
    with run(str(f), height=40) as h, and_exit(h):
        h.press('^End')
        h.await_cursor_position(x=0, y=36)
        with h.resize(width=80, height=5):
            h.await_cursor_position(x=0, y=2)
