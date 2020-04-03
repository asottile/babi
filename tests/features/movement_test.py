import pytest

from testing.runner import and_exit


def test_arrow_key_movement(run, tmpdir):
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
def test_page_up_and_page_down(run, ten_lines, page_up, page_down):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        h.press('Down')
        h.press('Down')
        h.press(page_up)
        h.await_cursor_position(x=0, y=1)

        h.press(page_down)
        h.await_text('line_8')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_6')

        h.press(page_up)
        h.await_text_missing('line_8')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_0')

        h.press(page_down)
        h.press(page_down)
        h.await_cursor_position(x=0, y=5)
        h.assert_cursor_line_equals('')
        h.press('Up')
        h.await_cursor_position(x=0, y=4)
        h.assert_cursor_line_equals('line_9')


def test_page_up_and_page_down_x_0(run, ten_lines):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        h.press('Right')
        h.press('PageDown')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_6')

        h.press('Right')
        h.press('PageUp')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_0')


def test_page_up_page_down_size_small_window(run, ten_lines):
    with run(str(ten_lines), height=4) as h, and_exit(h):
        h.press('PageDown')
        h.await_text('line_2')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_1')

        h.press('Down')
        h.press('PageUp')
        h.await_text_missing('line_2')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_0')


def test_ctrl_home(run, ten_lines):
    with run(str(ten_lines), height=4) as h, and_exit(h):
        for _ in range(3):
            h.press('PageDown')
        h.await_text_missing('line_0')

        h.press('^Home')
        h.await_text('line_0')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_end(run, ten_lines):
    with run(str(ten_lines), height=6) as h, and_exit(h):
        h.press('^End')
        h.await_cursor_position(x=0, y=3)
        h.assert_screen_line_equals(2, 'line_9')


def test_ctrl_end_already_on_last_page(run, ten_lines):
    with run(str(ten_lines), height=9) as h, and_exit(h):
        h.press('PageDown')
        h.await_cursor_position(x=0, y=1)
        h.await_text('line_9')

        h.press('^End')
        h.await_cursor_position(x=0, y=6)
        h.assert_screen_line_equals(5, 'line_9')


def test_scrolling_arrow_key_movement(run, ten_lines):
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
        h.assert_cursor_line_equals('line_8')
        # we should not have scrolled after 3 up presses
        for _ in range(3):
            h.press('Up')
        h.await_text('line_9')
        # but this should scroll up
        h.press('Up')
        h.await_text('line_0')


def test_ctrl_down_beginning_of_file(run, ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Down')
        h.await_text('line_3')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_1')


def test_ctrl_up_moves_screen_up_one_line(run, ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Down')
        h.press('^Up')
        h.await_text('line_0')
        h.await_text('line_2')
        h.await_cursor_position(x=0, y=2)


def test_ctrl_up_at_beginning_of_file_does_nothing(run, ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^Up')
        h.await_text('line_0')
        h.await_text('line_2')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_up_at_bottom_of_screen(run, ten_lines):
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


def test_ctrl_down_at_end_of_file(run, ten_lines):
    with run(str(ten_lines), height=5) as h, and_exit(h):
        h.press('^End')
        for i in range(4):
            h.press('^Down')
        h.press('Up')
        h.await_text('line_9')
        h.assert_cursor_line_equals('line_9')


def test_ctrl_down_causing_cursor_movement_should_fix_x(run, tmpdir):
    f = tmpdir.join('f')
    f.write('line_1\n\nline_2\n\nline_3\n\nline_4\n')

    with run(str(f), height=5) as h, and_exit(h):
        h.press('Right')
        h.press('^Down')
        h.await_text_missing('\nline_1\n')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_up_causing_cursor_movement_should_fix_x(run, tmpdir):
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
        h.await_text_missing('line_3')
        h.await_cursor_position(x=0, y=3)


@pytest.mark.parametrize('k', ('End', '^E'))
def test_end_key(run, tmpdir, k):
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
def test_home_key(run, tmpdir, k):
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


def test_page_up_does_not_go_negative(run, ten_lines):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        for _ in range(8):
            h.press('Down')
        h.await_cursor_position(x=0, y=4)
        h.press('^Y')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('line_0')


@pytest.fixture
def jump_word_file(tmpdir):
    f = tmpdir.join('f')
    contents = '''\
hello world

hi

    this(is_some_code)  # comment
'''
    f.write(contents)
    yield f


def test_ctrl_right_jump_by_word(run, jump_word_file):
    with run(str(jump_word_file)) as h, and_exit(h):
        h.press('^Right')
        h.await_cursor_position(x=5, y=1)
        h.press('^Right')
        h.await_cursor_position(x=11, y=1)
        h.press('Left')
        h.await_cursor_position(x=10, y=1)
        h.press('^Right')
        h.await_cursor_position(x=11, y=1)
        h.press('^Right')
        h.await_cursor_position(x=0, y=3)
        h.press('^Right')
        h.await_cursor_position(x=2, y=3)
        h.press('^Right')
        h.await_cursor_position(x=4, y=5)
        h.press('^Right')
        h.await_cursor_position(x=8, y=5)
        h.press('^Right')
        h.await_cursor_position(x=11, y=5)
        h.press('Down')
        h.press('^Right')
        h.await_cursor_position(x=0, y=6)


def test_ctrl_left_jump_by_word(run, jump_word_file):
    with run(str(jump_word_file)) as h, and_exit(h):
        h.press('^Left')
        h.await_cursor_position(x=0, y=1)
        h.press('Right')
        h.await_cursor_position(x=1, y=1)
        h.press('^Left')
        h.await_cursor_position(x=0, y=1)
        h.press('PageDown')
        h.await_cursor_position(x=0, y=6)
        h.press('^Left')
        h.await_cursor_position(x=33, y=5)
        h.press('^Left')
        h.await_cursor_position(x=26, y=5)
        h.press('Home')
        h.press('Right')
        h.await_cursor_position(x=1, y=5)
        h.press('^Left')
        h.await_cursor_position(x=2, y=3)


def test_ctrl_right_triggering_scroll(run, jump_word_file):
    with run(str(jump_word_file), height=4) as h, and_exit(h):
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.press('^Right')
        h.await_cursor_position(x=0, y=1)
        h.assert_cursor_line_equals('hi')


def test_ctrl_left_triggering_scroll(run, jump_word_file):
    with run(str(jump_word_file)) as h, and_exit(h):
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.press('^Down')
        h.await_cursor_position(x=0, y=1)
        h.press('^Left')
        h.await_cursor_position(x=11, y=1)
        h.assert_cursor_line_equals('hello world')


def test_sequence_handling(run_only_fake):
    # this test is run with the fake runner since it simulates some situations
    # that are either impossible or due to race conditions (that we can only
    # force with the fake runner)
    with run_only_fake() as h, and_exit(h):
        h.press_sequence('\x1b[1;5C\x1b[1;5D test1')  # ^Left + ^Right
        h.await_text('test1')
        h.await_text_missing('unknown key')

        h.press_sequence('\x1bOH', '\x1bOF', ' test2')  # Home + End
        h.await_text('test1 test2')
        h.await_text_missing('unknown key')

        h.press_sequence(' tq', 'M-O', 'BSpace', 'est3')
        h.await_text('test1 test2 test3')
        h.await_text('unknown key')
        h.await_text('M-O')

        h.press('M-[')
        h.await_text_missing('M-O')
        h.await_text('M-[')

        h.press('M-O')
        h.await_text_missing('M-[')
        h.await_text('M-O')

        h.press_sequence(' tq', 'M-[', 'BSpace', 'est4')
        h.await_text('test1 test2 test3 test4')
        h.await_text_missing('M-O')
        h.await_text('M-[')

        # TODO: this is broken for now, not quite sure what to do with it
        h.press_sequence('\x1b', 'BSpace')
        h.await_text(r'\x1b(263)')

        # the sequences after here are "wrong" but I don't think a human
        # could type them

        h.press_sequence(' tq', '\x1b[1;', 'BSpace', 'est5')
        h.await_text('test1 test2 test3 test4 test5')
        h.await_text(r'\x1b[1;')

        h.press_sequence('\x1b[111', ' test6')
        h.await_text('test1 test2 test3 test4 test5 test6')
        h.await_text(r'\x1b[111')

        h.press('\x1b[1;')
        h.press(' test7')
        h.await_text('test1 test2 test3 test4 test5 test6 test7')
        h.await_text(r'\x1b[1;')


def test_indentation_using_tabs(run, tmpdir):
    f = tmpdir.join('f')
    f.write(
        f'123456789\n'
        f'\t12\t{"x" * 20}\n'
        f'\tnot long\n',
    )

    with run(str(f), width=20) as h, and_exit(h):
        h.await_text(
            '123456789\n'
            '    12  xxxxxxxxxxx»\n'
            '    not long\n',
        )

        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.press('Up')
        h.await_cursor_position(x=0, y=1)

        h.press('Right')
        h.await_cursor_position(x=1, y=1)
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.press('Up')
        h.await_cursor_position(x=1, y=1)

        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        h.press('Right')
        h.await_cursor_position(x=4, y=2)
        h.press('Up')
        h.await_cursor_position(x=4, y=1)


def test_movement_with_wide_characters(run, tmpdir):
    f = tmpdir.join('f')
    f.write(
        f'{"🙃" * 20}\n'
        f'a{"🙃" * 20}\n',
    )

    with run(str(f), width=20) as h, and_exit(h):
        h.await_text(
            '🙃🙃🙃🙃🙃🙃🙃🙃🙃»»\n'
            'a🙃🙃🙃🙃🙃🙃🙃🙃🙃»\n',
        )

        for _ in range(10):
            h.press('Right')
        h.await_text(
            '««🙃🙃🙃🙃🙃🙃🙃🙃»»\n'
            'a🙃🙃🙃🙃🙃🙃🙃🙃🙃»\n',
        )

        for _ in range(6):
            h.press('Right')
        h.await_text(
            '««🙃🙃🙃🙃🙃🙃🙃\n'
            'a🙃🙃🙃🙃🙃🙃🙃🙃🙃»\n',
        )

        h.press('Down')
        h.await_text(
            '🙃🙃🙃🙃🙃🙃🙃🙃🙃»»\n'
            '«🙃🙃🙃🙃🙃🙃🙃🙃\n',
        )

        h.press('Left')
        h.await_text(
            '🙃🙃🙃🙃🙃🙃🙃🙃🙃»»\n'
            '«🙃🙃🙃🙃🙃🙃🙃🙃🙃»\n',
        )
