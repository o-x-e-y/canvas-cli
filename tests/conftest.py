"""Offline test rig.

`responses` intercepts every request, and the payloads below are written by
hand in the shapes the live API returns, including the awkward ones the code
exists for: unrated rubric criteria that keep a rating_id, course names that
repeat every semester, pagination through Link headers, and a 401 that means
either a bad token or a refused action.

Nothing here touches a real course.
"""

import json
import sys
import time
from pathlib import Path

import pytest
import responses

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from canvas_cli import api, cli

BASE = "https://canvas.test"
API = BASE + "/api/v1"
RUNNING = {"name": "2627nj", "start_at": "2026-09-01T00:00:00Z", "end_at": "2099-01-31T23:00:00Z"}
ENDED = {"name": "2526vj", "start_at": "2026-02-01T00:00:00Z", "end_at": "2026-08-29T22:00:00Z"}
PERSONAL = {"id": 7, "name": "Jane Doe personal course", "term": RUNNING}
GENERAL = {"id": 21, "name": "CMK", "term": RUNNING}
COURSE = f"{API}/courses/7"
MODULE = {"id": 70, "name": "Semester 3"}
SETTINGS = {
    "courses": {"personal": {"id": 7, "indent": 1}, "general": {"id": 21}},
    "defaults": {"assignment": "personal", "outcomes": "personal", "delete": "personal"},
}


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    key = tmp_path / "key"
    key.write_text("secret-token\n")
    config = tmp_path / "config"
    (config / "canvas").mkdir(parents=True)
    path = config / "canvas/settings.json"
    path.write_text(json.dumps({"url": BASE + "/", "api_key_file": str(key), **SETTINGS}))
    monkeypatch.setattr(api, "CONFIG_HOME", config)
    api.settings.cache_clear()
    api.session.cache_clear()
    return path


@pytest.fixture
def canvas():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


@pytest.fixture
def personal(canvas):
    """The personal course and its first module."""
    canvas.get(COURSE, json=PERSONAL)
    canvas.get(f"{COURSE}/modules", json=[MODULE, {"id": 71, "name": "Semester 2"}])
    return canvas


def run(*argv):
    cli.main(list(argv))


def body(call):
    return json.loads(call.request.body)


def calls(canvas, method, url):
    return [c for c in canvas.calls if c.request.method == method and c.request.url == url]


@pytest.fixture(autouse=True)
def utc(monkeypatch):
    monkeypatch.setenv("TZ", "UTC")
    time.tzset()


# A POSIX rule rather than "Europe/Amsterdam", which needs tzdata the Nix
# build sandbox does not have
AMSTERDAM = "CET-1CEST,M3.5.0,M10.5.0/3"


def timezone(monkeypatch, name):
    monkeypatch.setenv("TZ", name)
    time.tzset()
