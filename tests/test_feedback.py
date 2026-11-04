import json

import pytest
from conftest import API, run

from canvas_cli import feedback

ME = 1
COURSE = {"id": 21, "name": "CMK", "term": {"end_at": "2099-01-01T00:00:00Z"}}
ENDED = {"id": 20, "name": "Old", "term": {"end_at": "2020-01-01T00:00:00Z"}}

CRITERION = {
    "id": "c1",
    "description": "Analysis-S2 ",
    "ratings": [
        {"id": "r1", "description": "Proficient"},
        {"id": "r2", "description": "Beginning"},
    ],
}


def submission(**fields):
    return {
        "id": 300,
        "grade": None,
        "graded_at": None,
        "assignment": {"name": "Plan", "rubric": [CRITERION]},
        "submission_comments": [],
        **fields,
    }


@pytest.fixture
def state(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(feedback, "STATE_PATH", path)
    return path


def serve(canvas, *submissions):
    canvas.get(f"{API}/users/self", json={"id": ME})
    canvas.get(f"{API}/courses", json=[COURSE, ENDED])
    canvas.get(f"{API}/courses/21/students/submissions", json=list(submissions))


def test_first_run_only_records(canvas, state, capsys):
    comment = {"id": 1, "author_id": 2, "author_name": "Teacher", "comment": "Nice"}
    serve(canvas, submission(submission_comments=[comment]))

    run("feedback")

    assert capsys.readouterr().out.startswith("First run: recorded 1 existing items")
    assert json.loads(state.read_text()) == ["comment:1"]


def test_reports_new_comments_and_assessments_once(canvas, state, capsys):
    state.write_text(json.dumps(["comment:1"]))
    comments = [
        {"id": 1, "author_id": 2, "author_name": "Teacher", "comment": "Old"},
        {"id": 2, "author_id": ME, "author_name": "Me", "comment": "Mine"},
        {"id": 3, "author_id": 2, "author_name": "Teacher", "comment": "New"},
    ]
    serve(
        canvas,
        submission(
            submission_comments=comments,
            grade="complete",
            graded_at="2026-11-01T10:00:00Z",
            rubric_assessment={"c1": {"rating_id": "r1", "points": 3, "comments": "clear"}},
        ),
    )

    run("feedback")

    assert capsys.readouterr().out == (
        "CMK: Plan\nTeacher: New\n\n"
        "CMK: Plan\nAssessed\nGrade: complete\nAnalysis-S2: Proficient (clear)\n\n"
    )
    assert json.loads(state.read_text()) == [
        "assessed:300:2026-11-01T10:00:00Z",
        "comment:1",
        "comment:3",
    ]


def test_unrated_criterion_keeps_its_rating_id_but_has_no_points():
    text = feedback.assessment(
        submission(grade=None, rubric_assessment={"c1": {"rating_id": "r2", "points": None}})
    )
    assert text == "Analysis-S2: not rated"
