from __future__ import annotations

import functools
import os.path
import re
import subprocess

from babi import linting

ErrorsByHook = tuple[tuple[str, tuple[linting.Error, ...]], ...]

HOOK_ID_RE = re.compile('^- hook id: (.*)$')


def _parse_pre_commit(s: str) -> ErrorsByHook:
    ret = []
    current_hookid = ''
    current_lines: list[str] = []

    def _push_current_hook_id() -> None:
        nonlocal current_hookid

        if not current_hookid:
            return

        parsed = linting.parse_generic_output('\n'.join(current_lines))
        if parsed:
            ret.append((current_hookid, parsed))

    for line in s.splitlines():
        hook_id_match = HOOK_ID_RE.match(line)
        if hook_id_match:
            _push_current_hook_id()
            current_hookid = hook_id_match[1]
            current_lines.clear()
        else:
            current_lines.append(line)

    _push_current_hook_id()

    return tuple(ret)


class PreCommit:
    def __init__(self) -> None:
        self._root = functools.cache(self._root_uncached)

    def _root_uncached(self, filename: str) -> str:
        return subprocess.check_output(
            (
                'git', '-C', os.path.dirname(os.path.abspath(filename)),
                'rev-parse', '--show-toplevel',
            ),
            text=True,
            stderr=subprocess.DEVNULL,
        ).rstrip()

    def command(self, filename: str, scope: str) -> tuple[str, ...] | None:
        try:
            root = self._root(filename)
        except subprocess.CalledProcessError:
            return None  # not in a git repo!

        # no pre-commit config!
        cfg = os.path.join(root, '.pre-commit-config.yaml')
        if not os.path.exists(cfg):
            return None

        return (
            'pre-commit', 'run',
            '--color=never',
            '--config', cfg,
            '--files', filename,
        )

    def parse(self, filename: str, output: str) -> tuple[linting.Error, ...]:
        root = self._root(filename)

        def _norm(path: str) -> str:
            return os.path.relpath(path, root)

        filename = _norm(filename)
        return tuple(
            error._replace(msg=f'[{hook_id}] {error.msg}')
            for hook_id, errors in _parse_pre_commit(output)
            for error in errors
            if _norm(os.path.join(root, error.filename)) == filename
        )
