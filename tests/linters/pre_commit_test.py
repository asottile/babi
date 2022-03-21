from __future__ import annotations

import subprocess

import pytest

from babi import linting
from babi.linters.pre_commit import _parse_pre_commit
from babi.linters.pre_commit import PreCommit


def test_parse_pre_commit_noop():
    assert _parse_pre_commit('') == ()


def test_parse_pre_commit_output():
    s = '''\
[WARNING] Unstaged files detected.
[INFO] Stashing unstaged files to /home/runner/.cache/pre-commit/patch1647305583-1605.
fix requirements.txt.................................(no files to check)Skipped
fix double quoted strings................................................Failed
- hook id: double-quote-string-fixer
- exit code: 1

Fixing strings in tests/linting_test.py

flake8...................................................................Failed
- hook id: flake8
- exit code: 1

tests/linting_test.py:3:25: E271 multiple spaces after keyword
tests/linting_test.py:6:1: F401 'babi.linting.wat' imported but unused

autopep8.................................................................Passed
mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

tests/linting_test.py:6: error: Module "babi.linting" has no attribute "wat"
Found 1 error in 1 file (checked 1 source file)

[INFO] Restored changes from /home/runner/.cache/pre-commit/patch1647305583-1605.
'''  # noqa: E501
    ret = _parse_pre_commit(s)
    assert ret == (
        (
            'flake8',
            (
                linting.Error(
                    filename='tests/linting_test.py',
                    lineno=3,
                    col_offset=25,
                    msg='E271 multiple spaces after keyword',
                ),
                linting.Error(
                    filename='tests/linting_test.py',
                    lineno=6,
                    col_offset=1,
                    msg="F401 'babi.linting.wat' imported but unused",
                ),
            ),
        ),
        (
            'mypy',
            (
                linting.Error(
                    filename='tests/linting_test.py',
                    lineno=6,
                    col_offset=1,
                    msg='error: Module "babi.linting" has no attribute "wat"',
                ),
            ),
        ),
    )


def test_command_returns_none_not_in_git_dir(tmpdir):
    with tmpdir.as_cwd():
        assert PreCommit().command('t.py', 'source.python') is None


def test_command_returns_none_abspath_to_file(tmpdir):
    path = str(tmpdir.join('t.py'))
    assert PreCommit().command(path, 'source.python') is None


@pytest.fixture
def tmpdir_git(tmpdir):
    subprocess.check_call(('git', 'init', '-q', str(tmpdir)))
    yield tmpdir


def test_command_returns_none_no_pre_commit_config(tmpdir_git):
    path = str(tmpdir_git.join('t.py'))
    assert PreCommit().command(path, 'source.python') is None


def test_command_returns_when_config_exists(tmpdir_git):
    tmpdir_git.join('.pre-commit-config.yaml').write('{}\n')
    path = str(tmpdir_git.join('t.py'))
    ret = PreCommit().command(path, 'source.python')
    assert ret == ('pre-commit', 'run', '--color=never', '--files', path)


def test_filters_file_paths_to_actual_file(tmpdir_git):
    output = '''\
mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

t.py:6: error: error 1
u.py:7: error: error 2
'''
    with tmpdir_git.as_cwd():
        ret = PreCommit().parse('t.py', output)

    assert ret == (
        linting.Error('t.py', 6, 1, '[mypy] error: error 1'),
    )


def test_matches_files_with_absolute_paths(tmpdir_git):
    t_py_abspath = str(tmpdir_git.join('t.py'))
    output = f'''\
mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

{t_py_abspath}:6: error: error 1
'''
    with tmpdir_git.as_cwd():
        ret = PreCommit().parse('t.py', output)

    assert ret == (
        linting.Error(t_py_abspath, 6, 1, '[mypy] error: error 1'),
    )


def test_normalizes_paths_to_repo_root(tmpdir_git):
    d = tmpdir_git.join('d').ensure_dir()

    output = '''\
mypy.....................................................................Failed
- hook id: mypy
- exit code: 1

d/t.py:6: error: error 1
'''
    with d.as_cwd():
        ret = PreCommit().parse('t.py', output)

    assert ret == (
        linting.Error('d/t.py', 6, 1, '[mypy] error: error 1'),
    )
