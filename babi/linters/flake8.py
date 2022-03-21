from __future__ import annotations

from babi import linting


class Flake8:
    def command(self, filename: str, scope: str) -> tuple[str, ...] | None:
        if scope != 'source.python':
            return None
        else:
            # TODO: forbid color output
            return ('flake8', filename)

    def parse(self, filename: str, output: str) -> tuple[linting.Error, ...]:
        return tuple(
            error._replace(msg=f'[flake8] {error.msg}')
            for error in linting.parse_generic_output(output)
        )
