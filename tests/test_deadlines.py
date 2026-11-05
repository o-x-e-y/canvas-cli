import responses
from conftest import AMSTERDAM, API, run, timezone


def test_due_items_by_local_day_and_missing_first(canvas, capsys, monkeypatch):
    timezone(monkeypatch, AMSTERDAM)
    canvas.get(
        f"{API}/planner/items",
        json=[
            {
                "course_id": 21,
                "context_name": "CMK",
                "plannable_type": "assignment",
                "plannable_date": "2026-11-06T15:00:00Z",
                "plannable": {"id": 1, "title": "Portfolio"},
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
        f"{API}/users/self/courses/21/assignments",
        json=[
            {
                "id": 1,
                "updated_at": "2026-10-01T09:00:00Z",
                "submission": {"submitted_at": "2026-11-04T12:00:00Z"},
            }
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
        "Courses: all you're enrolled in\n\n"
        "Past due and missing\n"
        "  Thu 03 Sep 18:00  CMK: Cut-the-Crêpe\n"
        "\n"
        "Fri 06 Nov\n"
        "  00:30  CMK: Demo  (calendar event)\n"
        "  16:00  CMK: Portfolio  (submitted)\n"
    )


def test_a_submission_from_before_the_assignment_changed_does_not_count(
    canvas, capsys, monkeypatch
):
    timezone(monkeypatch, AMSTERDAM)
    canvas.get(
        f"{API}/planner/items",
        json=[
            {
                "course_id": 21,
                "context_name": "CMK",
                "plannable_type": "assignment",
                "plannable_date": "2026-11-06T15:00:00Z",
                "plannable": {"id": 1, "title": "Retrospective"},
                "submissions": {"submitted": True, "graded": False},
            },
            {
                "course_id": 21,
                "context_name": "CMK",
                "plannable_type": "assignment",
                "plannable_date": "2026-11-06T15:00:00Z",
                "plannable": {"id": 2, "title": "Pitch"},
                "submissions": {"submitted": True, "graded": False},
            },
        ],
    )
    canvas.get(
        f"{API}/users/self/courses/21/assignments",
        match=[
            responses.matchers.query_param_matcher(
                {"assignment_ids[]": ["1", "2"], "include[]": "submission", "per_page": "100"}
            )
        ],
        json=[
            {
                "id": 1,
                "updated_at": "2026-11-04T23:32:05Z",
                "submission": {"submitted_at": "2026-10-12T10:45:03Z"},
            },
            {
                "id": 2,
                "updated_at": "2026-10-01T09:00:00Z",
                "submission": {"submitted_at": "2026-11-04T12:00:00Z"},
            },
        ],
    )
    canvas.get(f"{API}/users/self/missing_submissions", json=[])

    run("deadlines")

    assert capsys.readouterr().out == (
        "Courses: all you're enrolled in\n\n"
        "Fri 06 Nov\n  16:00  CMK: Retrospective\n  16:00  CMK: Pitch  (submitted)\n"
    )
