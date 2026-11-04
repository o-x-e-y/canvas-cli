import pytest
from conftest import API, COURSE, ENDED, GENERAL, PERSONAL, run

from canvas_cli.api import Error
from canvas_cli.courses import resolve

DELTA = {"id": 13, "name": "Delta", "term": ENDED, "enrollments": [{"type": "ta"}]}


def test_nickname_carries_the_course_settings(canvas):
    canvas.get(COURSE, json=PERSONAL)

    course = resolve("personal", "assignment")

    assert (course.id, course.name, course.nickname, course.indent) == (
        7,
        PERSONAL["name"],
        "personal",
        1,
    )


def test_default_comes_from_the_command(canvas):
    canvas.get(COURSE, json=PERSONAL)

    assert resolve(None, "outcomes").nickname == "personal"


def test_an_id_that_has_a_nickname_gets_its_settings(canvas):
    canvas.get(COURSE, json=PERSONAL)

    assert resolve("7", "hand-in").indent == 1


def test_without_default_or_c_it_says_what_to_pass(canvas):
    with pytest.raises(Error, match="canvas deadlines needs -c COURSE"):
        resolve(None, "deadlines")


def test_unknown_name_lists_nicknames_and_courses(canvas):
    canvas.get(f"{API}/courses", json=[GENERAL])

    with pytest.raises(Error, match='"Nope".*personal, general.*\n  CMK'):
        resolve("Nope", "hand-in")


def test_ended_course_warns_but_still_resolves(canvas, capsys):
    canvas.get(f"{API}/courses/13", json=DELTA)

    assert resolve("13", "modules").name == "Delta"
    assert "Delta ended on 2026-08-" in capsys.readouterr().err


def test_courses_lists_nicknames_terms_and_roles(canvas, capsys):
    canvas.get(
        f"{API}/courses",
        json=[
            DELTA,
            {
                **PERSONAL,
                "enrollments": [{"type": "teacher"}, {"type": "student"}, {"type": "teacher"}],
            },
            {**GENERAL, "enrollments": [{"type": "student"}]},
        ],
    )

    run("courses")

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["general", "21", "CMK", "2627nj,", "ends", "2099-01-31", "student"]
    assert lines[1].startswith("personal  7   Jane Doe personal course")
    assert lines[1].endswith("teacher, student")
    assert "ended 2026-08-" in lines[2] and lines[2].startswith("          13")
    assert lines[-1] == "Defaults: assignment → personal, outcomes → personal, delete → personal"


def test_modules_marks_where_new_assignments_go(canvas, capsys):
    canvas.get(COURSE, json=PERSONAL)
    item = {"indent": 1, "title": "Plan", "type": "Assignment", "position": 2}
    header = {"indent": 0, "title": "Group", "type": "SubHeader", "position": 1}
    canvas.get(
        f"{COURSE}/modules",
        json=[
            {"id": 70, "name": "Semester 3", "items": [header, item]},
            {"id": 71, "name": "Old", "items": []},
        ],
    )

    run("modules", "-c", "personal")

    assert capsys.readouterr().out == (
        "70  Semester 3  (new assignments go here)\n  Group\n    Plan\n71  Old\n"
    )
