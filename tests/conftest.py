"""Offline test rig.

`responses` intercepts every request, and the payloads below are written by
hand in the shapes the live API returns, including the awkward ones the code
exists for: unrated rubric criteria that keep a rating_id, course names that
repeat every semester, pagination through Link headers.

Nothing here touches a real course.
"""

import json
import sys
from pathlib import Path

import pytest
import responses

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from canvas_cli import api

BASE = "https://canvas.test"
API = BASE + "/api/v1"
PERSONAL = {"id": 7, "name": "Jane Doe personal course"}
COURSE = f"{API}/courses/7"
MODULE = {"id": 70, "name": "Semester 3"}


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    key = tmp_path / "key"
    key.write_text("secret-token\n")
    config = tmp_path / "config"
    (config / "canvas").mkdir(parents=True)
    (config / "canvas/settings.json").write_text(
        json.dumps({"url": BASE + "/", "api_key_file": str(key)})
    )
    monkeypatch.setattr(api, "CONFIG_HOME", config)
    api.settings.cache_clear()
    api.session.cache_clear()
    return config / "canvas/settings.json"


@pytest.fixture
def canvas():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


@pytest.fixture
def personal(canvas):
    """The personal course and its first module."""
    canvas.get(f"{API}/courses", json=[{"id": 3, "name": "Other course"}, PERSONAL])
    canvas.get(f"{COURSE}/modules", json=[MODULE, {"id": 71, "name": "Semester 2"}])
    return canvas


def run(monkeypatch, main, *args):
    monkeypatch.setattr(sys, "argv", ["prog", *args])
    main()


def body(call):
    return json.loads(call.request.body)


def calls(canvas, method, url):
    return [c for c in canvas.calls if c.request.method == method and c.request.url == url]
