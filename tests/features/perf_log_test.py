from __future__ import annotations

from testing.runner import and_exit


def test(run, tmpdir, ten_lines):
    f = tmpdir.join('f.log')
    with run(str(ten_lines), '--perf-log', str(f)) as h, and_exit(h):
        h.press('Right')
        h.press('Down')
    lines = f.read().splitlines()
    assert lines[0] == 'μs\tevent'
    expected = ['startup', 'KEY_RIGHT', 'KEY_DOWN', '^X']
    assert [line.split()[-1] for line in lines[1:]] == expected
    assert tmpdir.join('f.log.pstats').exists()
