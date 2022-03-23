from __future__ import annotations

import subprocess


def graceful_terminate(
        proc: subprocess.Popen[str],
        *,
        timeout: float = .1,
) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
