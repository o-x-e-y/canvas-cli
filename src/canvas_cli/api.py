import json
import os
import sys
from functools import cache
from pathlib import Path

import requests

CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")


@cache
def settings():
    path = Path(CONFIG_HOME, "canvas/settings.json")
    try:
        values = json.loads(path.read_text())
    except FileNotFoundError:
        values = {}
    missing = [key for key in ("url", "api_key_file") if not values.get(key)]
    if missing:
        sys.exit(
            f"Error: {path} needs {' and '.join(missing)}: the Canvas instance, "
            'such as "https://school.instructure.com", and a file holding an '
            "access token."
        )
    return values


def base_url():
    return settings()["url"].rstrip("/")


def api_url():
    return base_url() + "/api/v1"


@cache
def session():
    s = requests.Session()
    s.headers["Authorization"] = (
        "Bearer " + Path(settings()["api_key_file"]).expanduser().read_text().strip()
    )
    return s


def check(response):
    if not response.ok:
        sys.exit(
            f"Error: {response.request.method} {response.url} returned "
            f"{response.status_code}: {response.text}"
        )
    return response


def get(path, **params):
    return check(session().get(api_url() + path, params=params)).json()


def pages(path, **params):
    url = api_url() + path
    while url:
        response = check(session().get(url, params=params))
        yield response.json()
        url = response.links.get("next", {}).get("url")
        # The next link already carries the query string
        params = None


def get_all(path, **params):
    return [item for page in pages(path, **params) for item in page]


def post(path, body):
    return check(session().post(api_url() + path, json=body)).json()


def put(path, body):
    return check(session().put(api_url() + path, json=body)).json()


def delete(path):
    return check(session().delete(api_url() + path)).json()


def personal_course():
    courses = [
        course
        for course in get_all("/courses", enrollment_type="teacher", per_page=100)
        if course["name"].endswith("personal course")
    ]
    if len(courses) != 1:
        sys.exit(
            "Error: expected one course named '… personal course' where you "
            f"teach, found {len(courses)}."
        )
    return courses[0]
