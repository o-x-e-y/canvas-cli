import json

import pytest
from conftest import AMSTERDAM, API, GENERAL, calls, run, timezone

DUE = "2026-11-06T15:00:00Z"
PAST = "2026-09-03T16:00:00Z"


def planned(id, title, submitted=True):
    return {
        "course_id": 21,
        "context_name": "CMK",
        "plannable_type": "assignment",
        "plannable_date": DUE,
        "plannable": {"id": id, "title": title},
        "submissions": {"submitted": submitted, "graded": False},
    }


def assignment(id, name, edited, submitted=None, due=DUE):
    return {
        "id": id,
        "name": name,
        "course_id": 21,
        "due_at": due,
        "updated_at": edited,
        "course": {"name": "CMK"},
        "submission": {"submitted_at": submitted},
    }


def mark(id, at, override=900, marked=True):
    return {
        "id": override,
        "plannable_type": "assignment",
        "plannable_id": id,
        "marked_complete": marked,
        "deleted_at": None,
        "updated_at": at,
    }


def serve(canvas, items=(), assignments=(), missing=(), overrides=()):
    canvas.get(f"{API}/courses", json=[GENERAL])
    canvas.get(f"{API}/planner/items", json=list(items))
    canvas.get(f"{API}/users/self/courses/21/assignments", json=list(assignments))
    canvas.get(f"{API}/courses/21/assignments", json=list(assignments))
    canvas.get(f"{API}/users/self/missing_submissions", json=list(missing))
    canvas.get(f"{API}/planner/overrides", json=list(overrides))


def test_due_items_by_local_day_and_missing_first(canvas, capsys, monkeypatch):
    timezone(monkeypatch, AMSTERDAM)
    demo = {
        "context_name": "CMK",
        "plannable_type": "calendar_event",
        "plannable_date": "2026-11-05T23:30:00Z",
        "plannable": {"title": "Demo"},
        "submissions": False,
    }
    serve(
        canvas,
        items=[planned(1, "Portfolio"), demo],
        assignments=[assignment(1, "Portfolio", "2026-10-01T09:00:00Z", "2026-11-04T12:00:00Z")],
        missing=[{**assignment(3, "Cut-the-Crêpe", "2026-09-01T09:00:00Z", due=PAST)}],
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
    serve(
        canvas,
        items=[planned(1, "Retrospective"), planned(2, "Pitch")],
        assignments=[
            assignment(1, "Retrospective", "2026-11-04T23:32:05Z", "2026-10-12T10:45:03Z"),
            assignment(2, "Pitch", "2026-10-01T09:00:00Z", "2026-11-04T12:00:00Z"),
        ],
    )

    run("deadlines")

    assert capsys.readouterr().out == (
        "Courses: all you're enrolled in\n\n"
        "Fri 06 Nov\n  16:00  CMK: Retrospective\n  16:00  CMK: Pitch  (submitted)\n"
    )


def test_past_due_follows_the_same_rule(canvas, capsys, monkeypatch):
    timezone(monkeypatch, AMSTERDAM)
    serve(
        canvas,
        assignments=[
            # Reused: edited after the hand-in, before the deadline
            assignment(1, "Retrospective", "2026-09-01T09:00:00Z", "2026-08-20T10:00:00Z", PAST),
            # Edited after its deadline, which can't have moved the deadline
            assignment(2, "Share", "2026-09-18T11:37:15Z", "2026-09-03T09:55:12Z", PAST),
            # Never handed in, and Canvas lists it as missing already
            assignment(3, "Plan", "2026-08-01T09:00:00Z", None, PAST),
        ],
        missing=[assignment(3, "Plan", "2026-08-01T09:00:00Z", None, PAST)],
    )

    run("deadlines", "--days", "1")

    assert capsys.readouterr().out == (
        "Courses: all you're enrolled in\n\n"
        "Past due and missing\n"
        "  Thu 03 Sep 18:00  CMK: Plan\n"
        "  Thu 03 Sep 18:00  CMK: Retrospective\n"
        "\n"
        "Nothing due in the next 1 days.\n"
    )


def test_a_planner_mark_counts_until_the_next_edit(canvas, capsys, monkeypatch):
    timezone(monkeypatch, AMSTERDAM)
    serve(
        canvas,
        items=[planned(1, "Retrospective"), planned(2, "Pitch", submitted=False)],
        assignments=[
            assignment(1, "Retrospective", "2026-11-04T23:00:00Z", "2026-10-12T10:00:00Z"),
            assignment(2, "Pitch", "2026-11-04T23:00:00Z"),
            assignment(3, "Plan", "2026-08-01T09:00:00Z", None, PAST),
            assignment(4, "Notes", "2026-08-01T09:00:00Z", None, PAST),
        ],
        missing=[
            assignment(3, "Plan", "2026-08-01T09:00:00Z", None, PAST),
            assignment(4, "Notes", "2026-08-01T09:00:00Z", None, PAST),
        ],
        overrides=[
            mark(1, "2026-11-05T08:00:00Z", 901),
            mark(2, "2026-11-01T08:00:00Z", 902),
            mark(3, "2026-10-01T08:00:00Z", 903),
            mark(4, "2026-10-01T08:00:00Z", 904, marked=False),
        ],
    )

    run("deadlines")

    assert capsys.readouterr().out == (
        "Courses: all you're enrolled in\n\n"
        "Past due and missing\n"
        "  Thu 03 Sep 18:00  CMK: Notes\n"
        "\n"
        "Fri 06 Nov\n"
        "  16:00  CMK: Retrospective  (marked done)\n"
        "  16:00  CMK: Pitch\n"
    )


def test_done_marks_it_in_the_planner(canvas, capsys):
    serve(canvas, assignments=[assignment(1, "Retrospective", "2026-11-04T23:00:00Z")])
    canvas.post(f"{API}/planner/overrides", json={"id": 900})

    run("done", "Retrospective")

    [call] = calls(canvas, "POST", f"{API}/planner/overrides")
    assert json.loads(call.request.body) == {
        "plannable_type": "assignment",
        "plannable_id": 1,
        "marked_complete": True,
    }
    assert (
        capsys.readouterr().out
        == "Marked done in your Canvas planner: general (CMK): Retrospective\n"
    )


def test_done_renews_a_mark_from_before_the_last_edit(canvas):
    serve(
        canvas,
        assignments=[assignment(1, "Retrospective", "2026-11-04T23:00:00Z")],
        overrides=[mark(1, "2026-10-01T08:00:00Z")],
    )
    canvas.put(f"{API}/planner/overrides/900", json={"id": 900})

    run("done", "1")

    puts = calls(canvas, "PUT", f"{API}/planner/overrides/900")
    assert [json.loads(c.request.body) for c in puts] == [
        {"marked_complete": False},
        {"marked_complete": True},
    ]


def test_done_leaves_a_mark_that_still_counts(canvas, capsys):
    serve(
        canvas,
        assignments=[assignment(1, "Retrospective", "2026-11-04T23:00:00Z")],
        overrides=[mark(1, "2026-11-05T08:00:00Z")],
    )

    run("done", "Retrospective")

    assert not [c for c in canvas.calls if c.request.method != "GET"]
    assert capsys.readouterr().out == "Already marked done: general (CMK): Retrospective\n"


def test_done_needs_one_match(canvas):
    serve(
        canvas,
        assignments=[
            assignment(1, "Retrospective", "2026-11-04T23:00:00Z"),
            assignment(2, "Retrospective", "2026-11-04T23:00:00Z"),
        ],
    )

    with pytest.raises(
        SystemExit, match=r"pass its id:\n  general \(CMK\): Retrospective \(id: 1\)"
    ):
        run("done", "Retrospective")
    with pytest.raises(SystemExit, match='No assignment named "Pitch" in general'):
        run("done", "Pitch")
