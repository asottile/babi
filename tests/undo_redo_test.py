from testing.runner import and_exit


def test_nothing_to_undo_redo(run):
    with run() as h, and_exit(h):
        h.press('M-u')
        h.await_text('nothing to undo!')
        h.press('M-U')
        h.await_text('nothing to redo!')


def test_undo_redo(run):
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


def test_undo_redo_movement_interrupts_actions(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('Left')
        h.press('Right')
        h.press('world')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_text('hello')


def test_undo_redo_action_interrupts_actions(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.await_text('hello')
        h.press('BSpace')
        h.await_text_missing('hello')
        h.press('M-u')
        h.await_text('hello')
        h.press('world')
        h.await_text('helloworld')
        h.press('M-u')
        h.await_text_missing('world')
        h.await_text('hello')


def test_undo_redo_mixed_newlines(run, tmpdir):
    f = tmpdir.join('f')
    f.write_binary(b'foo\nbar\r\n')

    with run(str(f)) as h, and_exit(h):
        h.press('hello')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_text(' *')


def test_undo_redo_with_save(run, tmpdir):
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


def test_undo_redo_implicit_linebreak(run, tmpdir):
    f = tmpdir.join('f')

    def _assert_contents(s):
        assert f.read() == s

    with run(str(f)) as h, and_exit(h):
        h.press('hello')
        h.press('M-u')
        h.press('^S')
        h.await_text('saved!')
        h.run(lambda: _assert_contents(''))
        h.press('M-U')
        h.press('^S')
        h.await_text('saved!')
        h.run(lambda: _assert_contents('hello\n'))


def test_redo_cleared_after_action(run, tmpdir):
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('M-u')
        h.press('world')
        h.press('M-U')
        h.await_text('nothing to redo!')


def test_undo_no_action_when_noop(run):
    with run() as h, and_exit(h):
        h.press('hello')
        h.press('Enter')
        h.press('world')
        h.press('Down')
        h.press('^K')
        h.press('M-u')
        h.await_text('undo: text')
        h.await_cursor_position(x=0, y=2)


def test_undo_redo_causes_scroll(run):
    with run(height=8) as h, and_exit(h):
        for i in range(10):
            h.press('Enter')
        h.await_cursor_position(x=0, y=3)
        h.press('M-u')
        h.await_cursor_position(x=0, y=1)
        h.press('M-U')
        h.await_cursor_position(x=0, y=4)
