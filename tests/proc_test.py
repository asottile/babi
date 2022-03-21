from __future__ import annotations

import subprocess
from unittest import mock

from babi.proc import graceful_terminate


def test_graceful_terminate_integration_succeeds():
    proc = subprocess.Popen(('sleep', 'infinity'), text=True)
    graceful_terminate(proc)
    # might be -15 or -9
    assert proc.returncode is not None


def test_wait_raises_timeout():
    # kind of a bad test, but there for coverage
    e = subprocess.TimeoutExpired(('sleep', 'infinity'), .5)
    proc = mock.Mock(spec=subprocess.Popen, **{'wait.side_effect': (e, None)})

    graceful_terminate(proc, timeout=.5)

    proc.kill.assert_called_once_with()
    proc.wait.assert_has_calls((mock.call(timeout=.5), mock.call()))
