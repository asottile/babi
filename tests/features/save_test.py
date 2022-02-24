from __future__ import annotations

import pytest

from testing.runner import and_exit
from testing.runner import trigger_command_mode


def test_mixed_newlines(run, tmpdir):
    f = tmpdir.join('f')
    f.write_binary(b'foo\nbar\r\n')
    with run(str(f)) as h, and_exit(h):
        # should start as modified
        h.await_text('f *')
        h.await_text(r"mixed newlines will be converted to '\n'")


def test_modify_file_with_windows_newlines(run, tmpdir):
    f = tmpdir.join('f')
    f.write_binary(b'foo\r\nbar\r\n')
    with run(str(f)) as h, and_exit(h):
        # should not start modified
        h.await_text_missing('*')
        h.press('Enter')
        h.await_text('*')
        h.press('^S')
        h.await_text('saved!')
    assert f.read_binary() == b'\r\nfoo\r\nbar\r\n'


def test_saving_file_with_multiple_lines_at_end_maintains_those(run, tmpdir):
    f = tmpdir.join('f')
    f.write('foo\n\n')
    with run(str(f)) as h, and_exit(h):
        h.press('a')
        h.await_text('*')
        h.press('^S')
        h.await_text('saved!')

    assert f.read() == 'afoo\n\n'


def test_new_file(run):
    with run('this_is_a_new_file') as h, and_exit(h):
        h.await_text('this_is_a_new_file')
        h.await_text('(new file)')


def test_not_a_file(run, tmpdir):
    d = tmpdir.join('d').ensure_dir()
    with run(str(d)) as h, and_exit(h):
        h.await_text('<<new file>>')
        h.await_text('error! not a file: ')


def test_non_utf8_file(run, tmpdir):
    f = tmpdir.join('f')
    f.write_binary(b'\x98\xef\xa0\x12')

    with run(str(f)) as h, and_exit(h):
        h.await_text('error! not utf-8:')


def test_save_no_filename_specified(run, tmpdir):
    f = tmpdir.join('f')

    with run() as h, and_exit(h):
        h.press('hello world')
        h.press('^S')
        h.await_text('enter filename:')
        h.press_and_enter(str(f))
        h.await_text('saved! (1 line written)')
        h.await_text_missing('*')
    assert f.read() == 'hello world\n'


@pytest.mark.parametrize('k', ('Enter', '^C'))
def test_save_no_filename_specified_cancel(run, k):
    with run() as h, and_exit(h):
        h.press('hello world')
        h.press('^S')
        h.await_text('enter filename:')
        h.press(k)
        h.await_text('cancelled')


def test_saving_file_on_disk_changes(run, tmpdir):
    # TODO: this should show some sort of diffing thing or just allow overwrite
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.run(lambda: f.write('hello world'))

        h.press('^S')
        h.await_text('file changed on disk, not implemented')


def test_allows_saving_same_contents_as_modified_contents(run, tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.run(lambda: f.write('hello world\n'))
        h.press('hello world')
        h.await_text('hello world')

        h.press('^S')
        h.await_text('saved! (1 line written)')
        h.await_text_missing('*')

    assert f.read() == 'hello world\n'


def test_allows_saving_if_file_on_disk_does_not_change(run, tmpdir):
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


def test_save_file_when_it_did_not_exist(run, tmpdir):
    f = tmpdir.join('f')

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        h.press('^S')
        h.await_text('saved! (1 line written)')
        h.await_text_missing('*')

    assert f.read() == 'hello world\n'


def test_saving_file_permission_denied(run, tmpdir):
    f = tmpdir.join('f').ensure()
    f.chmod(0o400)

    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        h.press('^S')
        # the filename message is missing as it is too long to be captured
        h.await_text('cannot save file: [Errno 13] Permission denied:')
        h.await_text(' *')


def test_save_via_ctrl_o(run, tmpdir):
    f = tmpdir.join('f')
    with run(str(f)) as h, and_exit(h):
        h.press('hello world')
        h.press('^O')
        h.await_text('enter filename: ')
        h.press('Enter')
        h.await_text('saved! (1 line written)')
    assert f.read() == 'hello world\n'


def test_save_via_ctrl_o_set_filename(run, tmpdir):
    f = tmpdir.join('f')
    with run() as h, and_exit(h):
        h.press('hello world')
        h.press('^O')
        h.await_text('enter filename:')
        h.press_and_enter(str(f))
        h.await_text('saved! (1 line written)')
    assert f.read() == 'hello world\n'


def test_save_via_ctrl_o_new_filename(run, tmpdir):
    f = tmpdir.join('f')
    f.write('wat\n')
    with run(str(f)) as h, and_exit(h):
        h.press('^O')
        h.await_text('enter filename: ')
        h.press_and_enter('new')
        h.await_text('saved! (1 line written)')
    assert f.read() == 'wat\n'
    assert tmpdir.join('fnew').read() == 'wat\n'


@pytest.mark.parametrize('key', ('^C', 'Enter'))
def test_save_via_ctrl_o_cancelled(run, key):
    with run() as h, and_exit(h):
        h.press('hello world')
        h.press('^O')
        h.await_text('enter filename:')
        h.press(key)
        h.await_text('cancelled')


def test_save_via_ctrl_o_position(run):
    with run('filename') as h, and_exit(h):
        h.press('hello world')
        h.press('^O')
        h.await_text('enter filename: filename')
        h.await_cursor_position(x=24, y=23)
        h.press('^C')


def test_save_on_exit_cancel_yn(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        h.press('^X')
        h.await_text('file is modified - save [yes, no]?')
        h.press('^C')
        h.await_text('cancelled')


def test_save_on_exit_cancel_filename(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        h.press('^X')
        h.await_text('file is modified - save [yes, no]?')
        h.press('y')
        h.await_text('enter filename:')
        h.press('^C')
        h.await_text('cancelled')


def test_save_on_exit(run, tmpdir):
    f = tmpdir.join('f')
    with run(str(f)) as h:
        h.press('hello')
        h.await_text('hello')
        h.press('^X')
        h.await_text('file is modified - save [yes, no]?')
        h.press('y')
        h.await_text(f'enter filename: {f}')
        h.press('Enter')
        h.await_exit()


def test_save_on_exit_resize(run, tmpdir):
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        h.press('^X')
        h.await_text('file is modified - save [yes, no]?')
        with h.resize(width=10, height=24):
            h.await_text('file is m…')
        h.await_text('file is modified - save [yes, no]?')
        h.press('^C')
        h.await_text('cancelled')


def test_vim_save_on_exit_cancel_yn(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        trigger_command_mode(h)
        h.press_and_enter(':q')
        h.await_text('file is modified - save [yes, no]?')
        h.press('^C')
        h.await_text('cancelled')


def test_vim_save_on_exit(run, tmpdir):
    f = tmpdir.join('f')
    with run(str(f)) as h:
        h.press('hello')
        h.await_text('hello')
        trigger_command_mode(h)
        h.press_and_enter(':q')
        h.await_text('file is modified - save [yes, no]?')
        h.press('y')
        h.await_text('enter filename: ')
        h.press('Enter')
        h.await_exit()


def test_vim_force_exit(run, tmpdir):
    f = tmpdir.join('f')
    with run(str(f)) as h:
        h.press('hello')
        h.await_text('hello')
        trigger_command_mode(h)
        h.press_and_enter(':q!')
        h.await_exit()


def test_save_on_exit_with_not_existing_directory(run, tmpdir):
    f = tmpdir.join('test/nested/dirs/f')
    with run(str(f)) as h:
        h.press('hello')
        h.await_text('hello')
        h.press('^X')
        h.await_text('file is modified - save [yes, no]?')
        h.press('y')
        h.await_text('enter filename: ')
        h.press('Enter')
        h.await_exit()
    assert f.read() == 'hello\n'


def test_save_to_current_directory(run, tmpdir):
    with tmpdir.as_cwd():
        f = tmpdir.join('f')
        with run(str(f)) as h:
            h.press('hello')
            h.await_text('hello')
            h.press_and_enter('^X')
            h.await_text('file is modified - save [yes, no]?')
            h.press('y')
            h.await_text('enter filename: ')
            h.press('Enter')
            h.await_exit()
        assert f.read() == 'hello\n'
