import collections
import contextlib
import os.path
from typing import Dict
from typing import Generator
from typing import List

from babi.user_data import xdg_data


class History:
    def __init__(self) -> None:
        self._orig_len: Dict[str, int] = collections.defaultdict(int)
        self.data: Dict[str, List[str]] = collections.defaultdict(list)
        self.prev: Dict[str, str] = {}

    @contextlib.contextmanager
    def save(self) -> Generator[None, None, None]:
        history_dir = xdg_data('history')
        os.makedirs(history_dir, exist_ok=True)
        for filename in os.listdir(history_dir):
            with open(os.path.join(history_dir, filename)) as f:
                self.data[filename] = f.read().splitlines()
                self._orig_len[filename] = len(self.data[filename])
        try:
            yield
        finally:
            for k, v in self.data.items():
                new_history = v[self._orig_len[k]:]
                if new_history:
                    with open(os.path.join(history_dir, k), 'a+') as f:
                        f.write('\n'.join(new_history) + '\n')
