import json

import pytest
from conftest import AMSTERDAM, API, timezone
from responses import matchers

from canvas_cli import api


def test_missing_settings_name_what_is_missing(settings):
    settings.write_text(json.dumps({"url": "https://canvas.test"}))
    with pytest.raises(api.Error, match="needs api_key_file"):
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


def test_a_bad_token_says_to_make_a_new_one(canvas):
    canvas.get(
        f"{API}/users/self", status=401, json={"errors": [{"message": "Invalid access token."}]}
    )
    with pytest.raises(api.Error, match="rejected the access token in .*key.*Make a new one"):
        api.get("/users/self")


def test_a_refused_action_passes_on_canvas_message(canvas):
    canvas.post(
        f"{API}/courses/7/assignments",
        status=401,
        json={
            "status": "unauthorized",
            "errors": [{"message": "user not authorized to perform that action"}],
        },
    )
    with pytest.raises(
        api.Error, match="doesn't allow this: POST .*: user not authorized to perform that action"
    ):
        api.post("/courses/7/assignments", {})


def test_not_found_stays_not_found(canvas):
    canvas.get(
        f"{API}/courses/9",
        status=404,
        json={"errors": [{"message": "The specified resource does not exist."}]},
    )
    with pytest.raises(api.Error, match="^Not found: GET"):
        api.get("/courses/9")


def test_other_failures_show_the_status_and_message(canvas):
    canvas.post(f"{API}/courses/7/rubrics", status=400, json={"errors": {"title": ["too long"]}})
    with pytest.raises(api.Error, match="returned 400: .*too long"):
        api.post("/courses/7/rubrics", {})


def test_rate_limit_is_retried(canvas, monkeypatch):
    waits = []
    monkeypatch.setattr(api.time, "sleep", waits.append)
    canvas.get(f"{API}/users/self", status=403, body="403 Forbidden (Rate Limit Exceeded)")
    canvas.get(f"{API}/users/self", json={"id": 1})

    assert api.get("/users/self") == {"id": 1}
    assert waits == [1]


def test_local_dates_follow_the_local_timezone(monkeypatch):
    timezone(monkeypatch, AMSTERDAM)
    assert api.local_date("2026-10-11T22:30:00Z") == "2026-10-12"
