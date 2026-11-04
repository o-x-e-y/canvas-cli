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
