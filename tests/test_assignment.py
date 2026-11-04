import pytest
from conftest import API, BASE, COURSE, MODULE, body, calls, run

OUTCOMES = [
    {
        "outcome": {
            "id": 501,
            "title": "Analysis-S2 ",
            "description": '<link rel="stylesheet" href="x.css">Investigates the problem.',
            "points_possible": 4,
            "mastery_points": 3,
            "ratings": [{"description": "Proficient", "points": 4}],
        }
    }
]


def assignment(id, name, **fields):
    return {
        "id": id,
        "name": name,
        "description": "",
        "published": False,
        "submission_types": ["online_upload"],
        **fields,
    }


def not_in_module(canvas):
    canvas.get(f"{COURSE}/module_item_sequence", json={"items": []})


def test_publish_creates_and_publishes_without_submitting(personal):
    personal.get(f"{COURSE}/assignments", json=[])
    personal.post(f"{COURSE}/assignments", json=assignment(11, "Plan", published=True))
    not_in_module(personal)
    personal.post(f"{COURSE}/modules/{MODULE['id']}/items", json={})

    run("assignment", "--name", "Plan", "--desc", "<p>x</p>", "--publish")

    created = body(calls(personal, "POST", f"{COURSE}/assignments")[0])["assignment"]
    assert created["published"] is True
    assert created["description"] == "<p>x</p>"
    item = body(calls(personal, "POST", f"{COURSE}/modules/70/items")[0])["module_item"]
    assert item == {"type": "Assignment", "content_id": 11, "indent": 1}
    assert not calls(personal, "PUT", f"{COURSE}/assignments/11")
    assert not [c for c in personal.calls if "submissions" in c.request.url]


def test_without_publish_or_doc_it_stays_unpublished(personal):
    personal.get(f"{COURSE}/assignments", json=[])
    personal.post(f"{COURSE}/assignments", json=assignment(11, "Plan"))
    personal.get(f"{COURSE}/module_item_sequence", json={"items": [{}]})

    run("assignment", "--name", "Plan")

    created = body(calls(personal, "POST", f"{COURSE}/assignments")[0])["assignment"]
    assert created["published"] is False


def test_rubric_criteria_come_from_the_outcome(personal):
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES)
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    personal.get(f"{COURSE}/module_item_sequence", json={"items": [{}]})
    personal.post(f"{COURSE}/rubrics", json={})

    run("assignment", "--name", "Plan", "--rubric", "Analysis-S2")

    rubric = body(calls(personal, "POST", f"{COURSE}/rubrics")[0])
    assert rubric["rubric"]["criteria"]["0"] == {
        "description": "Analysis-S2",
        "long_description": "Investigates the problem.",
        "points": 4,
        "learning_outcome_id": 501,
        "mastery_points": 3,
        "ratings": {"0": {"description": "Proficient", "points": 4}},
    }
    assert rubric["rubric_association"]["association_id"] == 11
    assert not calls(personal, "POST", f"{COURSE}/assignments")


def test_existing_rubric_is_left_alone(personal, capsys):
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES)
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan", rubric=[{}])])
    personal.get(f"{COURSE}/module_item_sequence", json={"items": [{}]})

    run("assignment", "--name", "Plan", "--rubric", "Analysis-S2")

    assert not calls(personal, "POST", f"{COURSE}/rubrics")
    assert "already has a rubric" in capsys.readouterr().out


def test_unknown_outcome_stops_before_anything_is_created(personal):
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES)

    with pytest.raises(SystemExit, match="unknown outcome.*Design-S9"):
        run("assignment", "--name", "Plan", "--rubric", "Analysis-S2,Design-S9")
    assert not [c for c in personal.calls if c.request.method != "GET"]


def test_duplicate_names_list_the_ids(personal):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan"), assignment(12, "Plan")])

    with pytest.raises(SystemExit, match=r"2 assignments are named \"Plan\" \(ids: 11, 12\)"):
        run("assignment", "--name", "Plan")


def test_doc_publishes_and_submits_through_the_upload_url(personal, tmp_path):
    doc = tmp_path / "plan.pdf"
    doc.write_bytes(b"%PDF")
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    personal.get(f"{COURSE}/module_item_sequence", json={"items": [{}]})
    personal.put(f"{COURSE}/assignments/11", json={})
    personal.post(
        f"{COURSE}/assignments/11/submissions/self/files",
        json={"upload_url": "https://upload.test/x", "upload_params": {"key": "k"}},
    )
    personal.post("https://upload.test/x", json={"id": 99})
    personal.post(f"{COURSE}/assignments/11/submissions", json={})

    run("assignment", "--name", "Plan", "--doc", str(doc))

    assert body(calls(personal, "PUT", f"{COURSE}/assignments/11")[0]) == {
        "assignment": {"published": True}
    }
    preflight = body(calls(personal, "POST", f"{COURSE}/assignments/11/submissions/self/files")[0])
    assert preflight == {"name": "plan.pdf", "size": 4}
    submission = body(calls(personal, "POST", f"{COURSE}/assignments/11/submissions")[0])
    assert submission["submission"] == {"submission_type": "online_upload", "file_ids": [99]}


def other_courses(canvas):
    canvas.get(
        f"{API}/courses",
        json=[
            {"id": 20, "name": "CMK", "term": {"start_at": "2026-02-01T00:00:00Z"}},
            {"id": 21, "name": "CMK", "term": {"start_at": "2026-09-01T00:00:00Z"}},
        ],
    )


def test_course_hands_in_to_the_newest_semester(canvas, tmp_path):
    doc = tmp_path / "plan.pdf"
    doc.write_bytes(b"%PDF")
    other_courses(canvas)
    course = f"{API}/courses/21"
    canvas.get(f"{course}/assignments", json=[assignment(5, "Study plan")])
    canvas.post(
        f"{course}/assignments/5/submissions/self/files",
        json={"upload_url": "https://upload.test/x", "upload_params": {}},
    )
    canvas.post("https://upload.test/x", json={"id": 99})
    canvas.post(f"{course}/assignments/5/submissions", json={})

    run("hand-in", "--course", "CMK", "--name", "Study plan", "--doc", str(doc))

    assert calls(canvas, "POST", f"{course}/assignments/5/submissions")


def test_course_lists_its_assignments_when_the_name_is_off(canvas, tmp_path):
    other_courses(canvas)
    canvas.get(f"{API}/courses/21/assignments", json=[assignment(5, "Study plan")])

    with pytest.raises(SystemExit, match='no assignment named "Plan".*\n  Study plan'):
        run("hand-in", "--course", "CMK", "--name", "Plan", "--doc", str(tmp_path))


def test_course_refuses_assignments_without_file_upload(canvas, tmp_path):
    other_courses(canvas)
    canvas.get(
        f"{API}/courses/21/assignments",
        json=[assignment(5, "Quiz", submission_types=["online_quiz"])],
    )

    with pytest.raises(SystemExit, match="takes online_quiz, not a file upload"):
        run("hand-in", "--course", "CMK", "--name", "Quiz", "--doc", str(tmp_path))


def test_delete_by_name_prints_the_undelete_page(personal, capsys):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    personal.delete(f"{COURSE}/assignments/11", json={})

    run("delete", "Plan")

    assert calls(personal, "DELETE", f"{COURSE}/assignments/11")
    assert f"{BASE}/courses/7/undelete" in capsys.readouterr().out


def test_delete_by_id(personal):
    personal.get(f"{COURSE}/assignments/12", json=assignment(12, "Plan"))
    personal.delete(f"{COURSE}/assignments/12", json={})

    run("delete", "12")

    assert calls(personal, "DELETE", f"{COURSE}/assignments/12")
