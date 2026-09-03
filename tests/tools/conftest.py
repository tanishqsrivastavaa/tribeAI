import pytest

from tribe.tools.base import ToolContext
from tribe.workspace import Workspace


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workspace=Workspace(tmp_path), timeout=10)
