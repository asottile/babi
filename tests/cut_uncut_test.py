from testing.runner import and_exit
from testing.runner import run


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
