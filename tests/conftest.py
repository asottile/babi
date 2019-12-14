import os
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def xdg_data_home(tmpdir):
    data_home = tmpdir.join('data_home')
    with mock.patch.dict(os.environ, {'XDG_DATA_HOME': str(data_home)}):
        yield data_home


@pytest.fixture
def ten_lines(tmpdir):
    f = tmpdir.join('f')
    f.write('\n'.join(f'line_{i}' for i in range(10)))
    yield f
