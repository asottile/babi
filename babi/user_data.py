import os.path


def xdg_data(*path: str) -> str:
    return os.path.join(
        os.environ.get('XDG_DATA_HOME') or
        os.path.expanduser('~/.local/share'),
        'babi', *path,
    )
