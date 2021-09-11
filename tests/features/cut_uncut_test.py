from __future__ import annotations

from testing.runner import and_exit


def test_cut_and_uncut(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('^K')
        h.await_text_missing('line_0')
        h.await_text(' *')
        h.press('^U')
        h.await_text('line_0')

        h.press('^Home')
        h.press('^K')
        h.press('^K')
        h.await_text_missing('line_1')
        h.press('^U')
        h.await_text('line_0')


def test_cut_at_beginning_of_file(run):
    with run() as h, and_exit(h):
        h.press('^K')
        h.press('^K')
        h.press('^K')
        h.await_text_missing('*')


def test_cut_end_of_file(run):
    with run() as h, and_exit(h):
        h.press('hi')
        h.press('Down')
        h.press('^K')
        h.press('hi')


def test_cut_end_of_file_noop_extra_cut(run):
    with run() as h, and_exit(h):
        h.press('hi')
        h.press('^K')
        h.press('^K')
        h.press('^U')
        h.await_text('hi')


def test_cut_uncut_multiple_file_buffers(run, tmpdir):
    f1 = tmpdir.join('f1')
    f1.write('hello\nworld\n')
    f2 = tmpdir.join('f2')
    f2.write('good\nbye\n')

    with run(str(f1), str(f2)) as h, and_exit(h):
        h.press('^K')
        h.await_text_missing('hello')
        h.press('^X')
        h.press('n')
        h.await_text_missing('world')
        h.press('^U')
        h.await_text('hello\ngood\nbye\n')


def test_selection_cut_uncut(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Right')
        h.press('S-Right')
        h.press('S-Down')
        h.press('^K')
        h.await_cursor_position(x=1, y=1)
        h.await_text('lne_1\n')
        h.await_text_missing('line_0')
        h.await_text(' *')
        h.press('^U')
        h.await_cursor_position(x=2, y=2)
        h.await_text('line_0\nline_1')


def test_selection_cut_uncut_backwards_select(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        for _ in range(3):
            h.press('Down')

        h.press('Right')
        h.press('S-Up')
        h.press('S-Up')
        h.press('S-Right')

        h.press('^K')
        h.await_text('line_0\nliine_3\nline_4\n')
        h.await_cursor_position(x=2, y=2)
        h.await_text(' *')

        h.press('^U')
        h.await_text('line_0\nline_1\nline_2\nline_3\nline_4\n')
        h.await_cursor_position(x=1, y=4)


def test_selection_cut_uncut_within_line(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Right')
        h.press('S-Right')
        h.press('S-Right')

        h.press('^K')
        h.await_text('le_0\n')
        h.await_cursor_position(x=1, y=1)
        h.await_text(' *')

        h.press('^U')
        h.await_text('line_0\n')
        h.await_cursor_position(x=3, y=1)


def test_selection_cut_uncut_selection_offscreen_y(run, ten_lines):
    with run(str(ten_lines), height=4) as h, and_exit(h):
        for _ in range(3):
            h.press('S-Down')
        h.await_text_missing('line_0')
        h.await_text('line_3')
        h.press('^K')
        h.await_text_missing('line_2')
        h.await_cursor_position(x=0, y=1)


def test_selection_cut_uncut_selection_offscreen_x(run):
    with run() as h, and_exit(h):
        h.press(f'hello{"o" * 100}')
        h.await_text_missing('hello')
        h.press('Home')
        h.await_text('hello')
        for _ in range(5):
            h.press('Right')
        h.press('S-End')
        h.await_text_missing('hello')
        h.press('^K')
        h.await_text('hello\n')


def test_selection_cut_uncut_at_end_of_file(run, ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('S-Down')
        h.press('S-Right')
        h.press('^K')
        h.await_text_missing('line_0')
        h.await_text_missing('line_1')
        h.await_text('ine_1')

        h.press('^End')
        h.press('^U')
        h.await_text('line_0\nl\n')
        h.await_cursor_position(x=1, y=11)

        h.press('Down')
        h.await_cursor_position(x=0, y=12)
