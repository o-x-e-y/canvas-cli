"""Replay the responses record.py recorded, so the code meets real shapes."""

import json

import pytest
from recording import DIR, SCENARIOS, replay


@pytest.mark.parametrize("name", SCENARIOS)
def test_recorded_output_is_unchanged(name):
    recording = json.loads((DIR / f"{name}.json").read_text())
    assert replay(recording) == (DIR / f"{name}.out").read_text()
