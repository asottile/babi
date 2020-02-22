def test_multiple_files(run, tmpdir):
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
