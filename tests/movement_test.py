import pytest

from testing.runner import and_exit
from testing.runner import run


def test_arrow_key_movement(tmpdir):
    f = tmpdir.join('f')
    f.write(
        'short\n'
        '\n'
        'long long long long\n',
    )
    with run(str(f)) as h, and_exit(h):
        h.await_text('short')
        h.await_cursor_position(x=0, y=1)
        # should not go off the beginning of the file
        h.press('Left')
        h.await_cursor_position(x=0, y=1)
        h.press('Up')
        h.await_cursor_position(x=0, y=1)
        # left and right should work
        h.press('Right')
        h.press('Right')
        h.await_cursor_position(x=2, y=1)
        h.press('Left')
        h.await_cursor_position(x=1, y=1)
        # up should still be a noop on line 1
        h.press('Up')
        h.await_cursor_position(x=1, y=1)
        # down once should put it on the beginning of the second line
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        # down again should restore the x positon on the next line
        h.press('Down')
        h.await_cursor_position(x=1, y=3)
        # down once more should put it on the special end-of-file line
        h.press('Down')
        h.await_cursor_position(x=0, y=4)
        # should not go off the end of the file
        h.press('Down')
        h.await_cursor_position(x=0, y=4)
        h.press('Right')
        h.await_cursor_position(x=0, y=4)
        # left should put it at the end of the line
        h.press('Left')
        h.await_cursor_position(x=19, y=3)
        # right should put it to the next line
        h.press('Right')
        h.await_cursor_position(x=0, y=4)
        # if the hint-x is too high it should not go past the end of line
        h.press('Left')
        h.press('Up')
        h.press('Up')
        h.await_cursor_position(x=5, y=1)
        # and moving back down should still retain the hint-x
        h.press('Down')
        h.press('Down')
        h.await_cursor_position(x=19, y=3)


@pytest.mark.parametrize(
    ('page_up', 'page_down'),
    (('PageUp', 'PageDown'), ('^Y', '^V')),
)
def test_page_up_and_page_down(ten_lines, page_up, page_down):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        h.press('Down')
        h.press('Down')
        h.press(page_up)
        h.await_cursor_position(x=0, y=1)

        h.press(page_down)
        h.await_text('line_8')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_6'

        h.press(page_up)
        h.await_text_missing('line_8')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_0'

        h.press(page_down)
        h.press(page_down)
        h.await_cursor_position(x=0, y=5)
        assert h.get_cursor_line() == ''
        h.press('Up')
        h.await_cursor_position(x=0, y=4)
        assert h.get_cursor_line() == 'line_9'


def test_page_up_page_down_size_small_window(ten_lines):
    with run(str(ten_lines), height=4) as h, and_exit(h):
        h.press('PageDown')
        h.await_text('line_2')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_1'

        h.press('Down')
        h.press('PageUp')
        h.await_text_missing('line_2')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_0'


def test_ctrl_home(ten_lines):
    with run(str(ten_lines), height=4) as h, and_exit(h):
        for _ in range(3):
            h.press('PageDown')
        h.await_text_missing('line_0')

        h.press('^Home')
        h.await_text('line_0')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_end(ten_lines):
    with run(str(ten_lines), height=6) as h, and_exit(h):
        h.press('^End')
        h.await_cursor_position(x=0, y=3)
        assert h.get_screen_line(2) == 'line_9'


def test_ctrl_end_already_on_last_page(ten_lines):
    with run(str(ten_lines), height=9) as h, and_exit(h):
        h.press('PageDown')
        h.await_cursor_position(x=0, y=1)
        h.await_text('line_9')

        h.press('^End')
        h.await_cursor_position(x=0, y=6)
        assert h.get_screen_line(5) == 'line_9'


def test_scrolling_arrow_key_movement(ten_lines):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        h.await_text('line_7')
        # we should not have scrolled after 7 presses
        for _ in range(7):
            h.press('Down')
        h.await_text('line_0')
        h.await_cursor_position(x=0, y=8)
        # but this should scroll down
        h.press('Down')
        h.await_text('line_8')
        h.await_cursor_position(x=0, y=4)
        assert h.get_cursor_line() == 'line_8'
        # we should not have scrolled after 3 up presses
        for _ in range(3):
            h.press('Up')
        h.await_text('line_9')
        # but this should scroll up
        h.press('Up')
        h.await_text('line_0')


def test_ctrl_down_beginning_of_file(ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Down')
        h.await_text('line_3')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_1'


def test_ctrl_up_moves_screen_up_one_line(ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Down')
        h.press('^Up')
        h.await_text('line_0')
        h.await_text('line_2')
        h.await_cursor_position(x=0, y=2)


def test_ctrl_up_at_beginning_of_file_does_nothing(ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Up')
        h.await_text('line_0')
        h.await_text('line_2')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_up_at_bottom_of_screen(ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Down')
        h.press('Down')
        h.press('Down')
        h.await_text('line_1')
        h.await_text('line_3')
        h.await_cursor_position(x=0, y=3)
        h.press('^Up')
        h.await_text('line_0')
        h.await_cursor_position(x=0, y=3)


def test_ctrl_down_at_end_of_file(ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^End')
        for i in range(4):
            h.press('^Down')
        h.press('Up')
        h.await_text('line_9')
        assert h.get_cursor_line() == 'line_9'


def test_ctrl_down_causing_cursor_movement_should_fix_x(tmpdir):
    f = tmpdir.join('f')
    f.write('line_1\n\nline_2\n\nline_3\n\nline_4\n')

    with run(str(f), height=5) as h, and_exit(h):
        h.press('Right')
        h.press('^Down')
        h.await_text_missing('\nline_1\n')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_up_causing_cursor_movement_should_fix_x(tmpdir):
    f = tmpdir.join('f')
    f.write('line_1\n\nline_2\n\nline_3\n\nline_4\n')

    with run(str(f), height=5) as h, and_exit(h):
        h.press('^Down')
        h.press('^Down')
        h.press('Down')
        h.press('Down')
        h.press('Right')
        h.await_text('line_3')
        h.press('^Up')
        h.await_text_missing('3')
        h.await_cursor_position(x=0, y=3)


@pytest.mark.parametrize('k', ('End', '^E'))
def test_end_key(tmpdir, k):
    f = tmpdir.join('f')
    f.write('hello world\nhello world\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.await_cursor_position(x=0, y=1)
        h.press(k)
        h.await_cursor_position(x=11, y=1)
        h.press('Down')
        h.await_cursor_position(x=11, y=2)


@pytest.mark.parametrize('k', ('Home', '^A'))
def test_home_key(tmpdir, k):
    f = tmpdir.join('f')
    f.write('hello world\nhello world\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Down')
        h.press('Left')
        h.await_cursor_position(x=11, y=1)
        h.press(k)
        h.await_cursor_position(x=0, y=1)
        h.press('Down')
        h.await_cursor_position(x=0, y=2)


def test_page_up_does_not_go_negative(ten_lines):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        for _ in range(8):
            h.press('Down')
        h.await_cursor_position(x=0, y=4)
        h.press('^Y')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_0'
