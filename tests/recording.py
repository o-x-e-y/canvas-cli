"""Recorded responses: real read-only Canvas answers, minus anything personal.

`record.py` runs each scenario against the live API and keeps only the fields
the code reads. It checks that those alone reproduce the live output, then
replaces names and titles with placeholders, masks free text, renumbers ids
and swaps the host, and saves the result with the output it gives.
`test_recorded.py` replays them.
"""

import contextlib
import io
import json
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import responses
from responses import matchers

from canvas_cli import announcements, api, cli, courses, deadlines, feedback

DIR = Path(__file__).parent / "recorded"
BASE = "https://canvas.test"
# A POSIX rule rather than "Europe/Amsterdam", which needs tzdata the Nix
# build sandbox does not have
AMSTERDAM = "CET-1CEST,M3.5.0,M10.5.0/3"
SCENARIOS = {
    "courses": ["courses"],
    "modules": ["modules", "-c", "{course}"],
    "outcomes": ["outcomes", "-c", "{course}"],
    "deadlines": ["deadlines"],
    "announcements": ["announcements", "--days", "60"],
    "feedback": ["feedback"],
}

FIELDS = {
    *("alignments", "assignment", "author_id", "author_name", "comment", "comments", "content_id"),
    *("context_code", "context_name", "course", "course_id", "deleted_at", "description"),
    *("due_at", "end_at", "enrollments", "excused", "grade", "graded", "graded_at", "hidden"),
    *("html_url", "id", "indent", "items", "late", "learning_outcome", "linked", "links"),
    *("marked_complete", "mastery_points", "message", "missing", "name", "outcome", "outcome_id"),
    *("outcome_results", "outcomes", "plannable", "plannable_date", "plannable_id"),
    *("plannable_type", "points", "points_possible", "posted_at", "rating_id", "ratings"),
    *("read_state", "restrict_enrollments_to_course_dates", "rollups", "rubric"),
    *("rubric_assessment", "score", "scores", "start_at", "submission", "submission_comments"),
    *("submissions", "submitted", "submitted_at", "submitted_or_assessed_at", "term", "title"),
    *("type", "updated_at", "user_name"),
}
# Objects keyed by data rather than by field name
KEYED_BY_ID = {"rubric_assessment"}
NAMES = {"name", "title", "author_name", "user_name", "context_name", "description"}
TEXT = {"comment", "comments", "message"}
SMALLEST_RENUMBERED = 1000


def keep_fields(value, keyed=False):
    if isinstance(value, list):
        return [keep_fields(v) for v in value]
    if isinstance(value, dict):
        return {
            k: keep_fields(v, k in KEYED_BY_ID) for k, v in value.items() if keyed or k in FIELDS
        }
    return value


def mask(text):
    """Each word to x and each number to 0, keeping HTML tags (without attributes) and
    entities."""
    parts = re.split(r"(<[^>]*>|&#?\w+;)", text)
    return "".join(
        re.sub(r"<(/?\w+)[^>]*>", r"<\1>", part)
        if part.startswith("<")
        else part
        if part.startswith("&")
        else re.sub(r"\d+", "0", re.sub(r"[^\W\d_]+", "x", part))
        for part in parts
    )


class Scrubber:
    def __init__(self, host):
        self.host = host
        self.ids = {}
        self.names = {}

    def collect_ids(self, value, key=None):
        if isinstance(value, list):
            for v in value:
                self.collect_ids(v, key)
        elif isinstance(value, dict):
            for k, v in value.items():
                self.collect_ids(v, k)
        elif (
            isinstance(value, int)
            and not isinstance(value, bool)
            and (key == "id" or str(key).endswith("_id"))
            and value >= SMALLEST_RENUMBERED
        ):
            self.ids.setdefault(value, 10000 + len(self.ids))

    def string(self, text):
        """Hosts and known ids in URLs, context codes and links; dates stay."""
        text = text.replace(self.host, BASE)
        return re.sub(
            r"(?<![\d-])\d{4,}(?![\d-])",
            lambda m: str(self.ids.get(int(m.group()), m.group())),
            text,
        )

    def name(self, key, text):
        stripped = text.strip()
        if not stripped:
            return text
        if stripped not in self.names:
            self.names[stripped] = f"{key.replace('_', ' ').capitalize()} {len(self.names) + 1}"
        return text.replace(stripped, self.names[stripped])

    def scrub(self, value, key=None):
        if isinstance(value, list):
            return [self.scrub(v, key) for v in value]
        if isinstance(value, dict):
            return {self.string(k): self.scrub(v, k) for k, v in value.items()}
        if isinstance(value, bool) or value is None:
            return value
        if isinstance(value, int):
            if key == "id" or str(key).endswith("_id"):
                return self.ids.get(value, value)
            return value
        if isinstance(value, str):
            if key in TEXT or (key == "description" and "<" in value):
                return mask(value)
            if key in NAMES:
                return self.name(key, value)
            return self.string(value)
        return value


def freeze(now):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz)

    stack = contextlib.ExitStack()
    for module in (announcements, courses, deadlines):
        stack.enter_context(mock.patch.object(module, "datetime", Frozen))
    return stack


@contextlib.contextmanager
def amsterdam():
    old = os.environ.get("TZ")
    os.environ["TZ"] = AMSTERDAM
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = old
        time.tzset()


@contextlib.contextmanager
def fresh_state():
    """Feedback with an empty state file, so it reports everything."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "canvas-feedback.json")
        path.write_text("[]")
        with mock.patch.object(feedback, "STATE_PATH", path):
            yield


def run(argv, now):
    out = io.StringIO()
    with freeze(now), amsterdam(), fresh_state(), contextlib.redirect_stdout(out):
        cli.main(argv)
    return out.getvalue()


@contextlib.contextmanager
def offline_settings(base, api_key_file=None):
    """Settings with no nicknames or defaults, so the output only depends on Canvas."""
    with tempfile.TemporaryDirectory() as tmp:
        key = api_key_file or Path(tmp, "key")
        if not api_key_file:
            key.write_text("secret-token\n")
        (Path(tmp) / "canvas").mkdir()
        Path(tmp, "canvas/settings.json").write_text(
            json.dumps({"url": base, "api_key_file": str(key)})
        )
        api.settings.cache_clear()
        api.session.cache_clear()
        with mock.patch.object(api, "CONFIG_HOME", tmp):
            yield
        api.settings.cache_clear()
        api.session.cache_clear()


def replay(recording, base=BASE):
    """The output of the recorded command, served the recorded responses."""
    with offline_settings(base), responses.RequestsMock() as canvas:
        for exchange in recording["exchanges"]:
            url = urlsplit(exchange["url"])
            canvas.add(
                exchange["method"],
                url._replace(query="").geturl(),
                json=exchange["json"],
                status=exchange["status"],
                headers={"Link": exchange["link"]} if exchange["link"] else {},
                match=[matchers.query_string_matcher(url.query)],
            )
        return run(recording["argv"], datetime.fromisoformat(recording["now"]))
