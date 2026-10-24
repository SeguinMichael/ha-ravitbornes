"""Shared fixtures for RavitBornes tests."""

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_json_fixture(name: str) -> dict[str, Any]:
    """Load an anonymized TomTom response from tests/fixtures/."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load integrations from custom_components/."""
    yield
