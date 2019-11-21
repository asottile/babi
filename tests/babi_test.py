import contextlib
import io
import shlex
import sys
from typing import List

import pytest
from hecate import Runner

import babi


def test_list_spy_repr():
    assert repr(babi.ListSpy(['a', 'b', 'c'])) == "ListSpy(['a', 'b', 'c'])"


def test_list_spy_item_retrieval():
    spy = babi.ListSpy(['a', 'b', 'c'])
    assert spy[1] == 'b'
    assert spy[-1] == 'c'
    with pytest.raises(IndexError):
        spy[3]


def test_list_spy_del():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    del spy[1]

    assert lst == ['a', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_del_with_negative():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    del spy[-1]

    assert lst == ['a', 'b']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_insert():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy.insert(1, 'q')

    assert lst == ['a', 'q', 'b', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_insert_with_negative():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy.insert(-1, 'q')

    assert lst == ['a', 'b', 'q', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_set_value():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy[1] = 'hello'

    assert lst == ['a', 'hello', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_multiple_modifications():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy[1] = 'hello'
    spy.insert(1, 'ohai')
    del spy[0]

    assert lst == ['ohai', 'hello', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_iter():
    spy = babi.ListSpy(['a', 'b', 'c'])
    spy_iter = iter(spy)
    assert next(spy_iter) == 'a'
    assert next(spy_iter) == 'b'
    assert next(spy_iter) == 'c'
    with pytest.raises(StopIteration):
        next(spy_iter)


def test_list_spy_append():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy.append('q')

    assert lst == ['a', 'b', 'c', 'q']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_pop_default():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy.pop()

    assert lst == ['a', 'b']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_list_spy_pop_idx():
    lst = ['a', 'b', 'c']

    spy = babi.ListSpy(lst)
    spy.pop(1)

    assert lst == ['a', 'c']

    spy.undo(lst)

    assert lst == ['a', 'b', 'c']


def test_position_repr():
    ret = repr(babi.File('f.txt'))
    assert ret == (
        'File(\n'
        "    filename='f.txt',\n"
        '    modified=False,\n'
        '    lines=[],\n'
        "    nl='\\n',\n"
        '    file_y=0,\n'
        '    cursor_y=0,\n'
        '    x=0,\n'
        '    x_hint=0,\n'
        '    sha256=None,\n'
        '    undo_stack=[],\n'
        '    redo_stack=[],\n'
        ')'
    )


@pytest.mark.parametrize(
    ('s', 'lines', 'nl', 'mixed'),
    (
        pytest.param('', [''], '\n', False, id='trivial'),
        pytest.param('1\n2\n', ['1', '2', ''], '\n', False, id='lf'),
        pytest.param('1\r\n2\r\n', ['1', '2', ''], '\r\n', False, id='crlf'),
        pytest.param('1\r\n2\n', ['1', '2', ''], '\n', True, id='mixed'),
        pytest.param('1\n2', ['1', '2', ''], '\n', False, id='noeol'),
    ),
)
def test_get_lines(s, lines, nl, mixed):
    # sha256 tested below
    ret_lines, ret_nl, ret_mixed, _ = babi._get_lines(io.StringIO(s))
    assert (ret_lines, ret_nl, ret_mixed) == (lines, nl, mixed)


def test_get_lines_sha256_checksum():
    ret = babi._get_lines(io.StringIO(''))
    sha256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    assert ret == ([''], '\n', False, sha256)


class PrintsErrorRunner(Runner):
    def __init__(self, *args, **kwargs):
        self._screenshots: List[str] = []
        super().__init__(*args, **kwargs)

    def screenshot(self, *args, **kwargs):
        ret = super().screenshot(*args, **kwargs)
        if not self._screenshots or self._screenshots[-1] != ret:
            self._screenshots.append(ret)
        return ret

    @contextlib.contextmanager
    def _onerror(self):
        try:
            yield
        except Exception:  # pragma: no cover
            # take a screenshot of the final state
            self.screenshot()
            print('=' * 79, flush=True)
            for screenshot in self._screenshots:
                print(screenshot, end='', flush=True)
                print('=' * 79, flush=True)
            raise

    def await_exit(self, *args, **kwargs):
        with self._onerror():
            return super().await_exit(*args, **kwargs)

    def await_text(self, text, timeout=None):
        """copied from the base implementation but doesn't munge newlines"""
        with self._onerror():
            for _ in self.poll_until_timeout(timeout):
                screen = self.screenshot()
                if text in screen:  # pragma: no branch
                    return
            raise AssertionError(
                f'Timeout while waiting for text {text!r} to appear',
            )

    def await_text_missing(self, s):
        """largely based on await_text"""
        with self._onerror():
            for _ in self.poll_until_timeout():
                screen = self.screenshot()
                munged = screen.replace('\n', '')
                if s not in munged:  # pragma: no branch
                    return
            raise AssertionError(
                f'Timeout while waiting for text {s!r} to disappear',
            )

    def get_pane_size(self):
        cmd = ('display', '-t0', '-p', '#{pane_width}\t#{pane_height}')
        w, h = self.tmux.execute_command(*cmd).split()
        return int(w), int(h)

    def _get_cursor_position(self):
        cmd = ('display', '-t0', '-p', '#{cursor_x}\t#{cursor_y}')
        x, y = self.tmux.execute_command(*cmd).split()
        return int(x), int(y)

    def await_cursor_position(self, *, x, y):
        with self._onerror():
            for _ in self.poll_until_timeout():
                pos = self._get_cursor_position()
                if pos == (x, y):  # pragma: no branch
                    return

            raise AssertionError(
                f'Timeout while waiting for cursor to reach {(x, y)}\n'
                f'Last cursor position: {pos}',
            )

    def get_screen_line(self, n):
        return self.screenshot().splitlines()[n]

    def get_cursor_line(self):
        _, y = self._get_cursor_position()
        return self.get_screen_line(y)

    @contextlib.contextmanager
    def resize(self, width, height):
        current_w, current_h = self.get_pane_size()
        sleep_cmd = (
            'bash', '-c',
            f'echo {"*" * (current_w * current_h)} && '
            f'exec sleep infinity',
        )

        panes = 0

        hsplit_w = current_w - width - 1
        if hsplit_w > 0:
            cmd = ('split-window', '-ht0', '-l', hsplit_w, *sleep_cmd)
            self.tmux.execute_command(*cmd)
            panes += 1

        vsplit_h = current_h - height - 1
        if vsplit_h > 0:  # pragma: no branch  # TODO
            cmd = ('split-window', '-vt0', '-l', vsplit_h, *sleep_cmd)
            self.tmux.execute_command(*cmd)
            panes += 1

        assert self.get_pane_size() == (width, height)
        try:
            yield
        finally:
            for _ in range(panes):
                self.tmux.execute_command('kill-pane', '-t1')

    def press_and_enter(self, s):
        self.press(s)
        self.press('Enter')


@contextlib.contextmanager
def run(*args, color=True, **kwargs):
    cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', *args)
    quoted = ' '.join(shlex.quote(p) for p in cmd)
    term = 'screen-256color' if color else 'screen'
    cmd = ('bash', '-c', f'export TERM={term}; exec {quoted}')
    with PrintsErrorRunner(*cmd, **kwargs) as h:
        h.await_text(babi.VERSION_STR)
        yield h


@contextlib.contextmanager
def and_exit(h):
    yield
    # only try and exit in non-exceptional cases
    h.press('^X')
    h.await_exit()


def trigger_command_mode(h):
    # in order to enter a steady state, trigger an unknown key first and then
    # press escape to open the command mode.  this is necessary as `Escape` is
    # the start of "escape sequences" and sending characters too quickly will
    # be interpreted as a single keypress
    h.press('^J')
    h.await_text('unknown key')
    h.press('Escape')
    h.await_text_missing('unknown key')


@pytest.fixture
def ten_lines(tmpdir):
    f = tmpdir.join('f')
    f.write('\n'.join(f'line_{i}' for i in range(10)))
    yield f


@pytest.mark.parametrize('color', (True, False))
def test_color_test(color):
    with run('--color-test', color=color) as h, and_exit(h):
        h.await_text('*  1*  2')


def test_can_start_without_color():
    with run(color=False) as h, and_exit(h):
        pass


def test_window_height_2(tmpdir):
    # 2 tall:
    # - header is hidden, otherwise behaviour is normal
    f = tmpdir.join('f.txt')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        with h.resize(80, 2):
            h.await_text_missing(babi.VERSION_STR)
            assert h.screenshot() == 'hello world\n\n'
            h.press('^J')
            h.await_text('unknown key')

        h.await_text(babi.VERSION_STR)


def test_window_height_1(tmpdir):
    # 1 tall:
    # - only file contents as body
    # - status takes precedence over body, but cleared after single action
    f = tmpdir.join('f.txt')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')

        with h.resize(80, 1):
            h.await_text_missing(babi.VERSION_STR)
            assert h.screenshot() == 'hello world\n'
            h.press('^J')
            h.await_text('unknown key')
            h.press('Right')
            h.await_text_missing('unknown key')
            h.press('Down')


def test_status_clearing_behaviour():
    with run() as h, and_exit(h):
        h.press('^J')
        h.await_text('unknown key')
        for i in range(24):
            h.press('LEFT')
        h.await_text('unknown key')
        h.press('LEFT')
        h.await_text_missing('unknown key')


def test_reacts_to_resize():
    with run() as h, and_exit(h):
        first_line = h.get_screen_line(0)
        with h.resize(40, 20):
            # the first line should be different after resize
            h.await_text_missing(first_line)


def test_mixed_newlines(tmpdir):
    f = tmpdir.join('f')
    f.write_binary(b'foo\nbar\r\n')
    with run(str(f)) as h, and_exit(h):
        # should start as modified
        h.await_text('f *')
        h.await_text(r"mixed newlines will be converted to '\n'")


def test_new_file():
    with run('this_is_a_new_file') as h, and_exit(h):
        h.await_text('this_is_a_new_file')
        h.await_text('(new file)')


def test_not_a_file(tmpdir):
    d = tmpdir.join('d').ensure_dir()
    with run(str(d)) as h, and_exit(h):
        h.await_text('<<new file>>')
        h.await_text("d' is not a file")


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


def test_prompt_window_width():
    with run() as h, and_exit(h):
        h.press('^_')
        h.await_text('enter line number:')
        h.press('123')
        with h.resize(width=23, height=24):
            h.await_text('\nenter line number: «3')
        with h.resize(width=22, height=24):
            h.await_text('\nenter line numb…: «3')
        with h.resize(width=7, height=24):
            h.await_text('\n…: «3')
        with h.resize(width=6, height=24):
            h.await_text('\n123')
        h.press('Enter')


def test_go_to_line_line(ten_lines):
    def _jump_to_line(n):
        h.press('^_')
        h.await_text('enter line number:')
        h.press_and_enter(str(n))
        h.await_text_missing('enter line number:')

    with run(str(ten_lines), height=9) as h, and_exit(h):
        # still on screen
        _jump_to_line(3)
        h.await_cursor_position(x=0, y=3)
        # should go to beginning of file
        _jump_to_line(0)
        h.await_cursor_position(x=0, y=1)
        # should go to end of the file
        _jump_to_line(999)
        h.await_cursor_position(x=0, y=4)
        assert h.get_screen_line(3) == 'line_9'
        # should also go to the end of the file
        _jump_to_line(-1)
        h.await_cursor_position(x=0, y=4)
        assert h.get_screen_line(3) == 'line_9'
        # should go to beginning of file
        _jump_to_line(-999)
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_0'


@pytest.mark.parametrize('key', ('Enter', '^C'))
def test_go_to_line_cancel(ten_lines, key):
    with run(str(ten_lines)) as h, and_exit(h):
        h.press('Down')
        h.await_cursor_position(x=0, y=2)

        h.press('^_')
        h.await_text('enter line number:')
        h.press(key)
        h.await_cursor_position(x=0, y=2)
        h.await_text('cancelled')


def test_go_to_line_not_an_integer():
    with run() as h, and_exit(h):
        h.press('^_')
        h.await_text('enter line number:')
        h.press_and_enter('asdf')
        h.await_text("not an integer: 'asdf'")


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
    f.write('1\n\n2\n\n3\n\n4\n')

    with run(str(f), height=5) as h, and_exit(h):
        h.press('Right')
        h.press('^Down')
        h.await_text_missing('\n1\n')
        h.await_cursor_position(x=0, y=1)


def test_ctrl_up_causing_cursor_movement_should_fix_x(tmpdir):
    f = tmpdir.join('f')
    f.write('1\n\n2\n\n3\n\n4\n')

    with run(str(f), height=5) as h, and_exit(h):
        h.press('^Down')
        h.press('^Down')
        h.press('Down')
        h.press('Down')
        h.press('Right')
        h.await_text('3')
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


def test_resize_scrolls_up(ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        h.await_text('line_9')

        for _ in range(7):
            h.press('Down')
        h.await_cursor_position(x=0, y=8)

        # a resize to a height of 10 should not scroll
        with h.resize(80, 10):
            h.await_text_missing('line_8')
            h.await_cursor_position(x=0, y=8)

        h.await_text('line_8')

        # but a resize to smaller should
        with h.resize(80, 9):
            h.await_text_missing('line_0')
            h.await_cursor_position(x=0, y=3)
            # make sure we're still on the same line
            assert h.get_cursor_line() == 'line_7'


def test_resize_scroll_does_not_go_negative(ten_lines):
    with run(str(ten_lines)) as h, and_exit(h):
        for _ in range(5):
            h.press('Down')
        h.await_cursor_position(x=0, y=6)

        with h.resize(80, 7):
            h.await_text_missing('line_9')
        h.await_text('line_9')

        for _ in range(2):
            h.press('Up')

        assert h.get_screen_line(1) == 'line_0'


def test_page_up_does_not_go_negative(ten_lines):
    with run(str(ten_lines), height=10) as h, and_exit(h):
        for _ in range(8):
            h.press('Down')
        h.await_cursor_position(x=0, y=4)
        h.press('^Y')
        h.await_cursor_position(x=0, y=1)
        assert h.get_cursor_line() == 'line_0'


def test_very_narrow_window_status():
    with run(height=50) as h, and_exit(h):
        with h.resize(5, 50):
            h.press('^J')
            h.await_text('unkno')


def test_horizontal_scrolling(tmpdir):
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


def test_horizontal_scrolling_exact_width(tmpdir):
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


def test_horizontal_scrolling_narrow_window(tmpdir):
    f = tmpdir.join('f')
    f.write(''.join(str(i) * 10 for i in range(10)))

    with run(str(f)) as h, and_exit(h):
        with h.resize(5, 24):
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


def test_window_width_1(tmpdir):
    f = tmpdir.join('f')
    f.write('hello')

    with run(str(f)) as h, and_exit(h):
        with h.resize(1, 24):
            h.await_text('»')
            for _ in range(3):
                h.press('Right')
        h.await_text('hello')
        h.await_cursor_position(x=3, y=1)


def test_basic_text_editing(tmpdir):
    with run() as h, and_exit(h):
        h.press('hello world')
        h.await_text('hello world')
        h.press('Down')
        h.press('bye!')
        h.await_text('bye!')
        assert h.screenshot().strip().endswith('world\nbye!')


def test_backspace_at_beginning_of_file():
    with run() as h, and_exit(h):
        h.press('Bspace')
        h.await_text_missing('unknown key')
        assert h.screenshot().strip().splitlines()[1:] == []
        assert '*' not in h.screenshot()


def test_backspace_joins_lines(tmpdir):
    f = tmpdir.join('f')
    f.write('foo\nbar\nbaz\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('foo')
        h.press('Down')
        h.press('Bspace')
        h.await_text('foobar')
        h.await_text('f *')
        h.await_cursor_position(x=3, y=1)
        # pressing down should retain the X position
        h.press('Down')
        h.await_cursor_position(x=3, y=2)


def test_backspace_at_end_of_file_still_allows_scrolling_down(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Down')
        h.press('Bspace')
        h.press('Down')
        h.await_cursor_position(x=0, y=2)
        assert '*' not in h.screenshot()


def test_backspace_deletes_text(tmpdir):
    f = tmpdir.join('f')
    f.write('ohai there')

    with run(str(f)) as h, and_exit(h):
        h.await_text('ohai there')
        for _ in range(3):
            h.press('Right')
        h.press('Bspace')
        h.await_text('ohi')
        h.await_text('f *')
        h.await_cursor_position(x=2, y=1)


def test_delete_at_end_of_file(tmpdir):
    with run() as h, and_exit(h):
        h.press('DC')
        h.await_text_missing('unknown key')
        h.await_text_missing('*')


def test_delete_removes_character_afterwards(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Right')
        h.press('DC')
        h.await_text('hllo world')
        h.await_text('f *')


def test_delete_at_end_of_line(tmpdir):
    f = tmpdir.join('f')
    f.write('hello\nworld\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello')
        h.press('Down')
        h.press('Left')
        h.press('DC')
        h.await_text('helloworld')
        h.await_text('f *')


def test_press_enter_beginning_of_file(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('Enter')
        h.await_text('\n\nhello world')
        h.await_cursor_position(x=0, y=2)
        h.await_text('f *')


def test_press_enter_mid_line(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        for _ in range(5):
            h.press('Right')
        h.press('Enter')
        h.await_text('hello\n world')
        h.await_cursor_position(x=0, y=2)
        h.press('Up')
        h.await_cursor_position(x=0, y=1)


def test_suspend(tmpdir):
    f = tmpdir.join('f')
    f.write('hello')

    with PrintsErrorRunner('bash', '--norc') as h:
        cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', str(f))
        h.press_and_enter(' '.join(shlex.quote(part) for part in cmd))
        h.await_text(babi.VERSION_STR)
        h.await_text('hello')

        h.press('^Z')
        h.await_text_missing('hello')

        h.press_and_enter('fg')
        h.await_text('hello')

        h.press('^X')
        h.press_and_enter('exit')
        h.await_exit()


def test_suspend_with_resize(tmpdir):
    f = tmpdir.join('f')
    f.write('hello')

    with PrintsErrorRunner('bash', '--norc') as h:
        cmd = (sys.executable, '-mcoverage', 'run', '-m', 'babi', str(f))
        h.press_and_enter(' '.join(shlex.quote(part) for part in cmd))
        h.await_text(babi.VERSION_STR)
        h.await_text('hello')

        h.press('^Z')
        h.await_text_missing('hello')

        with h.resize(80, 10):
            h.press_and_enter('fg')
            h.await_text('hello')

        h.press('^X')
        h.press_and_enter('exit')
        h.await_exit()


def test_multiple_files(tmpdir):
    a = tmpdir.join('file_a')
    a.write('a text')
    b = tmpdir.join('file_b')
    b.write('b text')
    c = tmpdir.join('file_c')
    c.write('c text')

    with run(str(a), str(b), str(c)) as h:
        h.await_text('file_a')
        h.await_text('[1/3]')
        h.await_text('a text')
        h.press('Right')
        h.await_cursor_position(x=1, y=1)

        h.press('M-Right')
        h.await_text('file_b')
        h.await_text('[2/3]')
        h.await_text('b text')
        h.await_cursor_position(x=0, y=1)

        h.press('M-Left')
        h.await_text('file_a')
        h.await_text('[1/3]')
        h.await_cursor_position(x=1, y=1)

        # wrap around
        h.press('M-Left')
        h.await_text('file_c')
        h.await_text('[3/3]')
        h.await_text('c text')

        # make sure to clear statuses when switching files
        h.press('^J')
        h.await_text('unknown key')
        h.press('M-Right')
        h.await_text_missing('unknown key')
        h.press('^J')
        h.await_text('unknown key')
        h.press('M-Left')
        h.await_text_missing('unknown key')

        # also make sure to clear statuses when exiting files
        h.press('^J')
        h.await_text('unknown key')
        h.press('^X')
        h.await_text('file_a')
        h.await_text_missing('unknown key')
        h.press('^X')
        h.await_text('file_b')
        h.press('^X')
        h.await_exit()


def test_saving_with_no_filename_doesnt_exist():
    # TODO: this should prompt but currently refuses
    with run() as h, and_exit(h):
        h.press('^S')
        h.await_text('no filename, not implemented')


def test_saving_file_on_disk_changes(tmpdir):
    # TODO: this should show some sort of diffing thing or just allow overwrite
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        f.write('hello world')

        h.press('^S')
        h.await_text('file changed on disk, not implemented')


def test_allows_saving_same_contents_as_modified_contents(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        f.write('hello world\n')
        h.press('hello world')
        h.await_text('hello world')

        h.press('^S')
        h.await_text('saved! (1 line written)')
        h.await_text_missing('*')

    assert f.read() == 'hello world\n'


def test_allows_saving_if_file_on_disk_does_not_change(tmpdir):
    f = tmpdir.join('f')
    f.write('hello world\n')

    with run(str(f)) as h, and_exit(h):
        h.await_text('hello world')
        h.press('ohai')
        h.press('Enter')

        h.press('^S')
        h.await_text('saved! (2 lines written)')
        h.await_text_missing('*')

    assert f.read() == 'ohai\nhello world\n'


def test_save_file_when_it_did_not_exist(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        h.press('^S')
        h.await_text('saved! (1 line written)')
        h.await_text_missing('*')

    assert f.read() == 'hello world\n'


def test_quit_via_colon_q():
    with run() as h:
        trigger_command_mode(h)
        h.press_and_enter(':q')
        h.await_exit()


def test_key_navigation_in_command_mode():
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press('hello world')
        h.await_cursor_position(x=11, y=23)
        h.press('Left')
        h.await_cursor_position(x=10, y=23)
        h.press('Right')
        h.await_cursor_position(x=11, y=23)
        h.press('Home')
        h.await_cursor_position(x=0, y=23)
        h.press('End')
        h.await_cursor_position(x=11, y=23)
        h.press('^A')
        h.await_cursor_position(x=0, y=23)
        h.press('^E')
        h.await_cursor_position(x=11, y=23)

        h.press('DC')  # does nothing at end
        h.await_cursor_position(x=11, y=23)
        h.await_text('\nhello world\n')

        h.press('Bspace')
        h.await_cursor_position(x=10, y=23)
        h.await_text('\nhello worl\n')

        h.press('Home')

        h.press('Bspace')  # does nothing at beginning
        h.await_cursor_position(x=0, y=23)
        h.await_text('\nhello worl\n')

        h.press('DC')
        h.await_cursor_position(x=0, y=23)
        h.await_text('\nello worl\n')

        # unknown keys don't do anything
        h.press('^J')
        h.await_text('\nello worl\n')

        h.press('Enter')


def test_save_via_command_mode(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        trigger_command_mode(h)
        h.press_and_enter(':w')

    assert f.read() == 'hello world\n'


def test_write_and_quit(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        trigger_command_mode(h)
        h.press_and_enter(':wq')
        h.await_exit()

    assert f.read() == 'hello world\n'


def test_resizing_and_scrolling_in_command_mode():
    with run(width=20) as h, and_exit(h):
        h.press('a' * 15)
        h.await_text(f'\n{"a" * 15}\n')
        trigger_command_mode(h)
        h.press('b' * 15)
        h.await_text(f'\n{"b" * 15}\n')

        with h.resize(width=16, height=24):
            h.await_text('\n«aaaaaa\n')  # the text contents
            h.await_text('\n«bbbbbb\n')  # the text contents
            h.await_cursor_position(x=7, y=23)
            h.press('Left')
            h.await_cursor_position(x=14, y=23)
            h.await_text(f'\n{"b" * 15}\n')

        h.press('Enter')


def test_invalid_command():
    with run() as h, and_exit(h):
        trigger_command_mode(h)
        h.press_and_enter(':fake')
        h.await_text('invalid command: :fake')


def test_empty_command_is_noop():
    with run() as h, and_exit(h):
        h.press('hello ')
        trigger_command_mode(h)
        h.press('Enter')
        h.press('world')
        h.await_text('hello world')
        h.await_text_missing('invalid command')


def test_cancel_command_mode():
    with run() as h, and_exit(h):
        h.press('hello ')
        trigger_command_mode(h)
        h.press(':q')
        h.press('^C')
        h.press('world')
        h.await_text('hello world')
        h.await_text_missing('invalid command')


def test_cut_and_uncut(ten_lines):
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


def test_cut_at_beginning_of_file():
    with run() as h, and_exit(h):
        h.press('^K')
        h.press('^K')
        h.press('^K')
        h.await_text_missing('*')


def test_cut_end_of_file():
    with run() as h, and_exit(h):
        h.press('hi')
        h.press('Down')
        h.press('^K')
        h.press('hi')


def test_cut_uncut_multiple_file_buffers(tmpdir):
    f1 = tmpdir.join('f1')
    f1.write('hello\nworld\n')
    f2 = tmpdir.join('f2')
    f2.write('good\nbye\n')

    with run(str(f1), str(f2)) as h, and_exit(h):
        h.press('^K')
        h.await_text_missing('hello')
        h.press('^X')
        h.await_text_missing('world')
        h.press('^U')
        h.await_text('hello\ngood\nbye\n')


def test_nothing_to_undo_redo():
    with run() as h, and_exit(h):
        h.press('M-u')
        h.await_text('nothing to undo!')
        h.press('M-U')
        h.await_text('nothing to redo!')


def test_undo_redo():
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_text_missing('hello')
        h.await_text_missing(' *')
        h.press('M-U')
        h.await_text('redo: text')
        h.await_text('hello')
        h.await_text(' *')


def test_undo_redo_movement_interrupts_actions():
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('Left')
        h.press('Right')
        h.press('world')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_text('hello')


def test_undo_redo_action_interrupts_actions():
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        h.press('Bspace')
        h.await_text_missing('hello')
        h.press('M-u')
        h.await_text('hello')
        h.press('world')
        h.await_text('helloworld')
        h.press('M-u')
        h.await_text_missing('world')
        h.await_text('hello')


def test_undo_redo_mixed_newlines(tmpdir):
    f = tmpdir.join('f')
    f.write_binary(b'foo\nbar\r\n')

    with run(str(f)) as h, and_exit(h):
        h.press('hello')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_text(' *')


def test_undo_redo_with_save(tmpdir):
    f = tmpdir.join('f').ensure()

    with run(str(f)) as h, and_exit(h):
        h.press('hello')
        h.press('^S')
        h.await_text_missing(' *')
        h.press('M-u')
        h.await_text(' *')
        h.press('M-U')
        h.await_text_missing(' *')
        h.press('M-u')
        h.await_text(' *')
        h.press('^S')
        h.await_text_missing(' *')
        h.press('M-U')
        h.await_text(' *')


def test_undo_redo_implicit_linebreak(tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello')
        h.press('M-u')
        h.press('^S')
        h.await_text('saved!')
        assert f.read() == ''
        h.press('M-U')
        h.press('^S')
        h.await_text('saved!')
        assert f.read() == 'hello\n'


def test_redo_cleared_after_action(tmpdir):
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('M-u')
        h.press('world')
        h.press('M-U')
        h.await_text('nothing to redo!')


def test_undo_no_action_when_noop():
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('Enter')
        h.press('world')
        h.press('Down')
        h.press('^K')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_cursor_position(x=0, y=2)


def test_undo_redo_causes_scroll():
    with run(height=8) as h, and_exit(h):
        for i in range(10):
            h.press('Enter')
        h.await_cursor_position(x=0, y=3)
        h.press('M-u')
        h.await_cursor_position(x=0, y=1)
        h.press('M-U')
        h.await_cursor_position(x=0, y=4)
