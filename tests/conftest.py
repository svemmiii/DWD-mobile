"""Test fixtures for DWD Mobile."""

from pathlib import Path
import sys

import pytest

# Ensure the repository root is importable in GitHub Actions/pytest so
# ``custom_components.dwd_mobile`` can be imported during collection.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in Home Assistant tests."""
    yield
