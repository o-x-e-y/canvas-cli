from conftest import AMSTERDAM, API, run, timezone


def test_due_items_by_local_day_and_missing_first(canvas, capsys, monkeypatch):
    timezone(monkeypatch, AMSTERDAM)
    canvas.get(
        f"{API}/planner/items",
        json=[
            {
                "context_name": "CMK",
                "plannable_type": "assignment",
                "plannable_date": "2026-11-06T15:00:00Z",
                "plannable": {"title": "Portfolio"},
                "submissions": {"submitted": True, "graded": False},
            },
            {
                "context_name": "CMK",
                "plannable_type": "calendar_event",
                "plannable_date": "2026-11-05T23:30:00Z",
                "plannable": {"title": "Demo"},
                "submissions": False,
            },
        ],
    )
    canvas.get(
        f"{API}/users/self/missing_submissions",
        json=[
            {
                "course_id": 21,
                "name": "Cut-the-Crêpe",
                "due_at": "2026-09-03T16:00:00Z",
                "course": {"name": "CMK"},
            }
        ],
    )

    run("deadlines")

    assert capsys.readouterr().out == (
        "Past due and missing\n"
        "  Thu 03 Sep 18:00  CMK: Cut-the-Crêpe\n"
        "\n"
        "Fri 06 Nov\n"
        "  00:30  CMK: Demo  (calendar event)\n"
        "  16:00  CMK: Portfolio  (submitted)\n"
    )
