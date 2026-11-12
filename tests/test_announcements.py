from datetime import UTC, datetime, timedelta

import pytest
from conftest import API, GENERAL, run

from canvas_cli.announcements import text


def test_html_becomes_paragraphs_and_lists():
    html = (
        "<p><span>Next week</span> it's time.</p>\n<h3>What to show?</h3>\n"
        "<ul>\n<li><span>What you </span><strong>built</strong></li>\n<li>What you learned</li>\n</ul>"
        "<p>Bye<br>Jane</p>"
    )
    assert text(html) == (
        "Next week it's time.\n\nWhat to show?\n\n- What you built\n- What you learned\n\nBye\nJane"
    )


def test_unread_only(canvas, capsys):
    canvas.get(f"{API}/courses", json=[GENERAL])
    post = {
        "context_code": "course_21",
        "posted_at": "2026-11-01T10:00:00Z",
        "user_name": "Teacher",
        "html_url": "https://canvas.test/x",
        "message": "<p>Hi</p>",
    }
    canvas.get(
        f"{API}/announcements",
        json=[
            {**post, "title": "Old", "read_state": "read"},
            {**post, "title": "New", "read_state": "unread"},
        ],
    )

    run("announcements", "--unread")

    out = capsys.readouterr().out
    assert "## CMK: New  (unread)" in out
    assert "Old" not in out
    assert "context_codes%5B%5D=course_21" in canvas.calls[-1].request.url


def test_mark_read_by_url(canvas, capsys):
    read = canvas.put(f"{API}/courses/21/discussion_topics/5/read", status=204)

    run("mark-read", "https://canvas.test/courses/21/discussion_topics/5")

    assert read.call_count == 1
    assert "Marked as read" in capsys.readouterr().out


def test_mark_read_refuses_other_urls_before_marking_any(canvas):
    read = canvas.put(f"{API}/courses/21/discussion_topics/5/read", status=204)

    with pytest.raises(SystemExit, match="https://canvas.test/x"):
        run(
            "mark-read",
            "https://canvas.test/courses/21/discussion_topics/5",
            "https://canvas.test/x",
        )

    assert read.call_count == 0


def test_mark_read_needs_urls_or_all(canvas):
    with pytest.raises(SystemExit, match="--all"):
        run("mark-read")


def test_mark_all_read_leaves_read_and_fresh_ones(canvas, capsys):
    canvas.get(f"{API}/courses", json=[GENERAL])
    now = datetime.now(UTC)
    post = {"context_code": "course_21", "posted_at": "2026-11-01T10:00:00Z"}
    canvas.get(
        f"{API}/announcements",
        json=[
            {**post, "id": 1, "title": "Seen", "read_state": "read"},
            {**post, "id": 2, "title": "Old", "read_state": "unread"},
            {
                **post,
                "id": 3,
                "title": "Fresh",
                "read_state": "unread",
                "posted_at": (now - timedelta(minutes=1)).isoformat(),
            },
        ],
    )
    read = canvas.put(f"{API}/courses/21/discussion_topics/2/read", status=204)

    run("mark-read", "--all", "--days", "9999")

    out = capsys.readouterr().out
    assert read.call_count == 1
    assert "Marked as read: CMK: Old" in out
    assert "Left unread, posted in the past 3 minutes: CMK: Fresh" in out
    assert "Seen" not in out
