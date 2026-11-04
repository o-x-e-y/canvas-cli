import json
import os
import time
from datetime import datetime
from functools import cache
from pathlib import Path

import requests

CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
TIMEOUT = (10, 60)
UPLOAD_TIMEOUT = (10, 600)
RATE_LIMIT_RETRIES = 4


class Error(Exception):
    pass


@cache
def settings():
    path = Path(CONFIG_HOME, "canvas/settings.json")
    try:
        values = json.loads(path.read_text())
    except FileNotFoundError:
        values = {}
    missing = [key for key in ("url", "api_key_file") if not values.get(key)]
    if missing:
        raise Error(
            f"{path} needs {' and '.join(missing)}: the Canvas instance, such as "
            '"https://school.instructure.com", and a file holding an access token.'
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


def message(response):
    try:
        errors = response.json().get("errors")
    except (ValueError, AttributeError):
        return response.text.strip()
    if isinstance(errors, list):
        return "; ".join(
            e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in errors
        )
    return str(errors or response.text.strip())


def check(response):
    if response.ok:
        return response
    request = f"{response.request.method} {response.url}"
    text = message(response)
    # Canvas answers 401 both for a bad token and for an action your role
    # can't do, so only the message tells them apart.
    if "access token" in text.lower():
        raise Error(
            f"Canvas rejected the access token in {settings()['api_key_file']} ({text}). "
            "Make a new one under Account, Settings."
        )
    if response.status_code == 404:
        raise Error(f"Not found: {request}")
    if response.status_code in (401, 403):
        raise Error(f"Canvas doesn't allow this: {request}: {text}")
    raise Error(f"{request} returned {response.status_code}: {text}")


def rate_limited(response):
    return response.status_code == 403 and "rate limit exceeded" in response.text.lower()


def request(method, url, **kwargs):
    for attempt in range(RATE_LIMIT_RETRIES):
        response = session().request(method, url, timeout=TIMEOUT, **kwargs)
        if not rate_limited(response):
            break
        time.sleep(2**attempt)
    return check(response)


def get(path, **params):
    return request("GET", api_url() + path, params=params).json()


def pages(path, **params):
    url = api_url() + path
    while url:
        response = request("GET", url, params=params)
        yield response.json()
        url = response.links.get("next", {}).get("url")
        # The next link already carries the query string
        params = None


def get_all(path, **params):
    return [item for page in pages(path, **params) for item in page]


def post(path, body):
    return request("POST", api_url() + path, json=body).json()


def put(path, body):
    return request("PUT", api_url() + path, json=body).json()


def delete(path):
    return request("DELETE", api_url() + path).json()


def upload(url, params, path):
    with path.open("rb") as f:
        response = requests.post(url, data=params, files={"file": f}, timeout=UPLOAD_TIMEOUT)
    return check(response).json()


def local(timestamp):
    """A Canvas timestamp, which is UTC, in the local timezone."""
    return datetime.fromisoformat(timestamp).astimezone()


def local_date(timestamp):
    return local(timestamp).date().isoformat() if timestamp else ""
