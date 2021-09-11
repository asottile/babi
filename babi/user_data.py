from __future__ import annotations

import os.path
import sys


def _xdg(*path: str, env: str, default: str) -> str:
    return os.path.join(
        os.environ.get(env) or os.path.expanduser(default),
        'babi', *path,
    )


def xdg_data(*path: str) -> str:
    return _xdg(*path, env='XDG_DATA_HOME', default='~/.local/share')


def xdg_config(*path: str) -> str:
    return _xdg(*path, env='XDG_CONFIG_HOME', default='~/.config')


def prefix_data(*path: str) -> str:
    return os.path.join(sys.prefix, 'share/babi', *path)
