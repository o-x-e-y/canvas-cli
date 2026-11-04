import json

import pytest
from conftest import API, PERSONAL
from responses import matchers

from canvas_cli import api


def test_missing_settings_name_what_is_missing(settings):
    settings.write_text(json.dumps({"url": "https://canvas.test"}))
    with pytest.raises(SystemExit, match="needs api_key_file"):
        api.settings()


def test_token_comes_from_the_key_file(canvas):
    canvas.get(f"{API}/users/self", json={"id": 1})
    api.get("/users/self")
    assert canvas.calls[0].request.headers["Authorization"] == "Bearer secret-token"


def test_get_all_follows_next_links_without_resending_params(canvas):
    next_url = f"{API}/courses?page=2&per_page=100"
    # Strict on the query, so a resent per_page fails instead of looping on page 1
    canvas.get(
        f"{API}/courses",
        json=[{"id": 1}],
        headers={"Link": f'<{next_url}>; rel="next"'},
        match=[matchers.query_string_matcher("per_page=100")],
    )
    canvas.get(next_url, json=[{"id": 2}])

    assert api.get_all("/courses", per_page=100) == [{"id": 1}, {"id": 2}]
    assert canvas.calls[1].request.url == next_url


def test_failed_request_exits_with_the_canvas_error(canvas):
    canvas.get(f"{API}/users/self", status=401, body='{"errors":"Invalid access token."}')
    with pytest.raises(SystemExit, match="GET .* returned 401: .*Invalid access token"):
        api.get("/users/self")


def test_personal_course_must_be_unique(canvas):
    canvas.get(f"{API}/courses", json=[PERSONAL, {**PERSONAL, "id": 8}])
    with pytest.raises(SystemExit, match="found 2"):
        api.personal_course()
