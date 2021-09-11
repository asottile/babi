from __future__ import annotations

import collections
import contextlib
import os.path
from typing import Generator

from babi.user_data import xdg_data


class History:
    def __init__(self) -> None:
        self._orig_len: dict[str, int] = collections.defaultdict(int)
        self.data: dict[str, list[str]] = collections.defaultdict(list)
        self.prev: dict[str, str] = {}

    @contextlib.contextmanager
    def save(self) -> Generator[None, None, None]:
        history_dir = xdg_data('history')
        os.makedirs(history_dir, exist_ok=True)
        for filename in os.listdir(history_dir):
            history_filename = os.path.join(history_dir, filename)
            with open(history_filename, encoding='UTF-8') as f:
                self.data[filename] = f.read().splitlines()
                self._orig_len[filename] = len(self.data[filename])
        try:
            yield
        finally:
            for k, v in self.data.items():
                new_history = v[self._orig_len[k]:]
                if new_history:
                    history_filename = os.path.join(history_dir, k)
                    with open(history_filename, 'a+', encoding='UTF-8') as f:
                        f.write('\n'.join(new_history) + '\n')
