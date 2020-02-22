from babi.main import File


def test_position_repr():
    ret = repr(File('f.txt'))
    assert ret == (
        'File(\n'
        "    filename='f.txt',\n"
        '    modified=False,\n'
        '    lines=[],\n'
        "    nl='\\n',\n"
        '    file_y=0,\n'
        '    y=0,\n'
        '    x=0,\n'
        '    x_hint=0,\n'
        '    sha256=None,\n'
        '    undo_stack=[],\n'
        '    redo_stack=[],\n'
        '    select_start=None,\n'
        ')'
    )
