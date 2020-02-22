import contextlib
import cProfile
import time
from typing import Generator
from typing import List
from typing import Optional
from typing import Tuple


class Perf:
    def __init__(self) -> None:
        self._prof: Optional[cProfile.Profile] = None
        self._records: List[Tuple[str, float]] = []
        self._name: Optional[str] = None
        self._time: Optional[float] = None

    def start(self, name: str) -> None:
        if self._prof:
            assert self._name is None, self._name
            self._name = name
            self._time = time.monotonic()
            self._prof.enable()

    def end(self) -> None:
        if self._prof:
            assert self._name is not None
            assert self._time is not None
            self._prof.disable()
            self._records.append((self._name, time.monotonic() - self._time))
            self._name = self._time = None

    @contextlib.contextmanager
    def log(self, filename: Optional[str]) -> Generator[None, None, None]:
        if filename is None:
            yield
        else:
            self._prof = cProfile.Profile()
            self.start('startup')
            try:
                yield
            finally:
                self.end()
                self._prof.dump_stats(f'{filename}.pstats')
                with open(filename, 'w') as f:
                    f.write('μs\tevent\n')
                    for name, duration in self._records:
                        f.write(f'{int(duration * 1000 * 1000)}\t{name}\n')
