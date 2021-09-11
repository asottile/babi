from __future__ import annotations

import os
from unittest import mock

from babi.user_data import xdg_data


def test_when_xdg_data_home_is_set():
    with mock.patch.dict(os.environ, {'XDG_DATA_HOME': '/foo'}):
        ret = xdg_data('history', 'command')
    assert ret == '/foo/babi/history/command'


def test_when_xdg_data_home_is_not_set():
    def fake_expanduser(s):
        return s.replace('~', '/home/username')

    with mock.patch.object(os.path, 'expanduser', fake_expanduser):
        with mock.patch.dict(os.environ, clear=True):
            ret = xdg_data('history')
    assert ret == '/home/username/.local/share/babi/history'
