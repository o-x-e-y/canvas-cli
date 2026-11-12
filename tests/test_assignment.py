from pathlib import Path

import pytest
from conftest import API, BASE, COURSE, GENERAL, body, calls, run

from canvas_cli import assignment as assignment_module

ANALYSIS = {
    "id": 501,
    "title": "Analysis-S2 ",
    "description": '<link rel="stylesheet" href="x.css">Investigates the problem.',
    "points_possible": 4,
    "mastery_points": 3,
    "ratings": [{"description": "Proficient", "points": 4}],
}
OUTCOMES = [{"outcome": ANALYSIS}]
ITEMS = f"{COURSE}/modules/70/items"


def assignment(id, name, **fields):
    return {
        "id": id,
        "name": name,
        "description": "",
        "published": False,
        "submission_types": ["online_upload"],
        **fields,
    }


def in_module(canvas, items):
    canvas.get(f"{COURSE}/module_item_sequence", json={"items": items})


def new_assignment(canvas, **fields):
    canvas.get(f"{COURSE}/assignments", json=[])
    canvas.post(f"{COURSE}/assignments", json=assignment(11, "Plan", **fields))
    in_module(canvas, [])
    canvas.post(ITEMS, json={})


def uploads(canvas, course_url, assignment_id, file_ids):
    files = f"{course_url}/assignments/{assignment_id}/submissions/self/files"
    for i, file_id in enumerate(file_ids):
        canvas.post(
            files, json={"upload_url": f"https://upload.test/{i}", "upload_params": {"key": "k"}}
        )
        canvas.post(f"https://upload.test/{i}", json={"id": file_id})
    canvas.post(f"{course_url}/assignments/{assignment_id}/submissions", json={})


def pdf(tmp_path, name="plan.pdf"):
    doc = tmp_path / name
    doc.write_bytes(b"%PDF")
    return doc


def test_publish_creates_and_publishes_without_submitting(personal):
    new_assignment(personal, published=True)

    run("assignment", "--name", "Plan", "--desc", "<p>x</p>", "--publish")

    created = body(calls(personal, "POST", f"{COURSE}/assignments")[0])["assignment"]
    assert created["published"] is True
    assert created["description"] == "<p>x</p>"
    item = body(calls(personal, "POST", ITEMS)[0])["module_item"]
    assert item == {"type": "Assignment", "content_id": 11, "indent": 1}
    assert not calls(personal, "PUT", f"{COURSE}/assignments/11")
    assert not [c for c in personal.calls if "submissions" in c.request.url]


def test_without_publish_or_doc_it_stays_unpublished(personal):
    personal.get(f"{COURSE}/assignments", json=[])
    personal.post(f"{COURSE}/assignments", json=assignment(11, "Plan"))
    in_module(personal, [{}])

    run("assignment", "--name", "Plan")

    created = body(calls(personal, "POST", f"{COURSE}/assignments")[0])["assignment"]
    assert created["published"] is False


def test_indent_flag_overrides_the_course_default(personal):
    new_assignment(personal)

    run("assignment", "--name", "Plan", "--indent", "0")

    assert body(calls(personal, "POST", ITEMS)[0])["module_item"]["indent"] == 0


def test_course_without_indent_setting_uses_zero(canvas):
    general = f"{API}/courses/21"
    canvas.get(general, json=GENERAL)
    canvas.get(f"{general}/modules", json=[{"id": 80, "name": "Week 1"}])
    canvas.get(f"{general}/assignments", json=[])
    canvas.post(f"{general}/assignments", json=assignment(11, "Plan"))
    canvas.get(f"{general}/module_item_sequence", json={"items": []})
    canvas.post(f"{general}/modules/80/items", json={})

    run("assignment", "-c", "general", "--name", "Plan")

    assert (
        body(calls(canvas, "POST", f"{general}/modules/80/items")[0])["module_item"]["indent"] == 0
    )


def test_configured_module_replaces_the_first(personal, settings):
    settings.write_text(settings.read_text().replace('"indent": 1}', '"indent": 1, "module": 71}'))
    new_assignment(personal)
    personal.get(f"{COURSE}/modules/71", json={"id": 71, "name": "Semester 2"})
    personal.post(f"{COURSE}/modules/71/items", json={})

    run("assignment", "--name", "Plan")

    assert calls(personal, "POST", f"{COURSE}/modules/71/items")
    assert not calls(personal, "POST", ITEMS)


ITEMS_WITH_GROUPS = [
    {"id": 1, "position": 1, "indent": 0, "type": "SubHeader", "title": "Personal Project"},
    {"id": 2, "position": 2, "indent": 1, "type": "Assignment", "title": "Plan A"},
    {"id": 3, "position": 3, "indent": 0, "type": "SubHeader", "title": "Group Project "},
    {"id": 4, "position": 4, "indent": 1, "type": "Assignment", "title": "Research"},
    {"id": 5, "position": 5, "indent": 1, "type": "Assignment", "title": "Design"},
]


def test_after_places_it_at_the_end_of_that_headers_group(personal):
    new_assignment(personal)
    personal.get(ITEMS, json=ITEMS_WITH_GROUPS)

    run("assignment", "--name", "Plan", "--after", "Personal Project")

    assert body(calls(personal, "POST", ITEMS)[0])["module_item"]["position"] == 3


def test_after_the_last_group_goes_to_the_end(personal):
    new_assignment(personal)
    personal.get(ITEMS, json=ITEMS_WITH_GROUPS)

    run("assignment", "--name", "Plan", "--after", "Group Project")

    assert body(calls(personal, "POST", ITEMS)[0])["module_item"]["position"] == 6


def test_after_an_unknown_header_lists_the_headers(personal):
    new_assignment(personal)
    personal.get(ITEMS, json=ITEMS_WITH_GROUPS)

    with pytest.raises(SystemExit, match='no header "Nope".*\n  Personal Project\n  Group Project'):
        run("assignment", "--name", "Plan", "--after", "Nope")
    assert not calls(personal, "POST", ITEMS)


def test_rubric_criteria_come_from_the_outcome(personal):
    personal.get(f"{COURSE}/rubrics", json=[])
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES)
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    in_module(personal, [{}])
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


def test_same_outcome_in_two_groups_is_not_ambiguous(personal):
    personal.get(f"{COURSE}/rubrics", json=[])
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES + OUTCOMES)
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    in_module(personal, [{}])
    personal.post(f"{COURSE}/rubrics", json={})

    run("assignment", "--name", "Plan", "--rubric", "Analysis-S2")

    assert calls(personal, "POST", f"{COURSE}/rubrics")


def test_repeated_titles_need_the_id(personal):
    other = {**ANALYSIS, "id": 502}
    personal.get(f"{COURSE}/rubrics", json=[])
    personal.get(f"{COURSE}/outcome_group_links", json=[*OUTCOMES, {"outcome": other}])

    with pytest.raises(SystemExit, match=r"Analysis-S2 matches 2 outcomes \(ids: 501, 502\)"):
        run("assignment", "--name", "Plan", "--rubric", "Analysis-S2")

    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    in_module(personal, [{}])
    personal.post(f"{COURSE}/rubrics", json={})
    run("assignment", "--name", "Plan", "--rubric", "502")
    criterion = body(calls(personal, "POST", f"{COURSE}/rubrics")[0])["rubric"]["criteria"]["0"]
    assert criterion["learning_outcome_id"] == 502


def test_existing_rubric_is_left_alone(personal, capsys):
    personal.get(f"{COURSE}/rubrics", json=[])
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES)
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan", rubric=[{}])])
    in_module(personal, [{}])

    run("assignment", "--name", "Plan", "--rubric", "Analysis-S2")

    assert not calls(personal, "POST", f"{COURSE}/rubrics")
    assert "already has a rubric" in capsys.readouterr().out


def test_unknown_outcome_stops_before_anything_is_created(personal):
    personal.get(f"{COURSE}/rubrics", json=[])
    personal.get(f"{COURSE}/outcome_group_links", json=OUTCOMES)

    with pytest.raises(SystemExit, match="Unknown outcome.*Design-S9 is not an outcome"):
        run("assignment", "--name", "Plan", "--rubric", "Analysis-S2,Design-S9")
    assert not [c for c in personal.calls if c.request.method != "GET"]


def test_missing_file_stops_before_anything_is_created(personal, tmp_path):
    with pytest.raises(SystemExit, match="No such file: .*nope.pdf"):
        run("assignment", "--name", "Plan", "--doc", str(tmp_path / "nope.pdf"))
    assert not personal.calls


def test_duplicate_names_list_the_ids(personal):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan"), assignment(12, "Plan")])

    with pytest.raises(SystemExit, match=r"2 assignments are named \"Plan\" \(ids: 11, 12\)"):
        run("assignment", "--name", "Plan")


def test_docs_publish_and_submit_through_the_upload_urls(personal, tmp_path):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    in_module(personal, [{}])
    personal.put(f"{COURSE}/assignments/11", json={})
    uploads(personal, COURSE, 11, [98, 99])

    run(
        "assignment",
        "--name",
        "Plan",
        "--doc",
        str(pdf(tmp_path)),
        "--doc",
        str(pdf(tmp_path, "b.pdf")),
    )

    assert body(calls(personal, "PUT", f"{COURSE}/assignments/11")[0]) == {
        "assignment": {"published": True}
    }
    slot = body(calls(personal, "POST", f"{COURSE}/assignments/11/submissions/self/files")[0])
    assert slot == {"name": "plan.pdf", "size": 4}
    submission = body(calls(personal, "POST", f"{COURSE}/assignments/11/submissions")[0])
    assert submission["submission"] == {"submission_type": "online_upload", "file_ids": [98, 99]}


def test_a_refused_step_says_which_and_that_a_rerun_continues(personal, tmp_path):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan", published=True)])
    in_module(personal, [{}])
    personal.post(
        f"{COURSE}/assignments/11/submissions/self/files",
        status=401,
        json={"errors": [{"message": "user not authorized to perform that action"}]},
    )

    with pytest.raises(SystemExit) as exit:
        run("assignment", "--name", "Plan", "--doc", str(pdf(tmp_path)))
    message = str(exit.value)
    assert "Canvas doesn't allow this" in message
    assert "user not authorized to perform that action" in message
    assert "while submitting the files" in message
    assert "Rerun the same command" in message


def newest_cmk(canvas):
    canvas.get(
        f"{API}/courses",
        json=[
            {"id": 20, "name": "CMK", "term": {"start_at": "2026-02-01T00:00:00Z"}},
            {"id": 22, "name": "CMK", "term": {"start_at": "2026-09-01T00:00:00Z"}},
        ],
    )
    return f"{API}/courses/22"


def test_hand_in_by_full_name_takes_the_newest_semester(canvas, tmp_path):
    course = newest_cmk(canvas)
    canvas.get(f"{course}/assignments", json=[assignment(5, "Study plan")])
    uploads(canvas, course, 5, [99])

    run("hand-in", "-c", "CMK", "--name", "Study plan", "--doc", str(pdf(tmp_path)))

    assert calls(canvas, "POST", f"{course}/assignments/5/submissions")


def test_hand_in_by_nickname(canvas):
    course = f"{API}/courses/21"
    canvas.get(course, json=GENERAL)
    canvas.get(
        f"{course}/assignments",
        json=[assignment(5, "Repo", submission_types=["online_url"])],
    )
    canvas.post(f"{course}/assignments/5/submissions", json={})

    run("hand-in", "-c", "general", "--name", "Repo", "--url", "https://git.test/x")

    submission = body(calls(canvas, "POST", f"{course}/assignments/5/submissions")[0])
    assert submission["submission"] == {
        "submission_type": "online_url",
        "url": "https://git.test/x",
    }


def test_hand_in_lists_the_assignments_when_the_name_is_off(canvas, tmp_path):
    course = newest_cmk(canvas)
    canvas.get(f"{course}/assignments", json=[assignment(5, "Study plan")])

    with pytest.raises(SystemExit, match='no assignment named "Plan".*\n  Study plan'):
        run("hand-in", "-c", "CMK", "--name", "Plan", "--doc", str(pdf(tmp_path)))


def test_hand_in_checks_the_submission_type(canvas, tmp_path):
    course = newest_cmk(canvas)
    canvas.get(
        f"{course}/assignments", json=[assignment(5, "Quiz", submission_types=["online_quiz"])]
    )

    with pytest.raises(SystemExit, match="takes online_quiz, not online_upload"):
        run("hand-in", "-c", "CMK", "--name", "Quiz", "--doc", str(pdf(tmp_path)))


def test_hand_in_by_id_fetches_that_assignment(canvas, tmp_path, capsys):
    course = newest_cmk(canvas)
    canvas.get(f"{course}/assignments/54321", json=assignment(54321, "Study plan"))
    uploads(canvas, course, 54321, [99])

    run("hand-in", "-c", "CMK", "--id", "54321", "--doc", str(pdf(tmp_path)))

    assert calls(canvas, "POST", f"{course}/assignments/54321/submissions")
    assert "Handing in to CMK: Study plan\n" in capsys.readouterr().out


def test_hand_in_by_an_unknown_id(canvas, tmp_path):
    course = newest_cmk(canvas)
    canvas.get(f"{course}/assignments/404", status=404, json={"errors": [{"message": "x"}]})

    with pytest.raises(SystemExit, match="CMK has no assignment with id 404"):
        run("hand-in", "-c", "CMK", "--id", "404", "--doc", str(pdf(tmp_path)))
    assert not calls(canvas, "POST", f"{course}/assignments/404/submissions")


def test_hand_in_without_a_default_needs_c(canvas, tmp_path):
    with pytest.raises(SystemExit, match="canvas hand-in needs -c COURSE.*personal, general"):
        run("hand-in", "--name", "Plan", "--doc", str(pdf(tmp_path)))
    assert not canvas.calls


def test_delete_by_name_asks_without_yes(personal, monkeypatch, capsys):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    personal.delete(f"{COURSE}/assignments/11", json={})
    monkeypatch.setattr(assignment_module.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    run("delete", "Plan")

    assert calls(personal, "DELETE", f"{COURSE}/assignments/11")
    assert f"{BASE}/courses/7/undelete" in capsys.readouterr().out


def test_delete_answered_no_deletes_nothing(personal, monkeypatch):
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    monkeypatch.setattr(assignment_module.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "")

    run("delete", "Plan")

    assert not calls(personal, "DELETE", f"{COURSE}/assignments/11")


def test_delete_without_a_terminal_needs_yes(personal):
    personal.get(f"{COURSE}/assignments/12", json=assignment(12, "Plan"))

    with pytest.raises(SystemExit, match="Pass --yes"):
        run("delete", "12")
    assert not calls(personal, "DELETE", f"{COURSE}/assignments/12")


def test_delete_by_id_with_yes(personal):
    personal.get(f"{COURSE}/assignments/12", json=assignment(12, "Plan"))
    personal.delete(f"{COURSE}/assignments/12", json={})

    run("delete", "12", "--yes")

    assert calls(personal, "DELETE", f"{COURSE}/assignments/12")


def test_form_fills_the_assignment(personal, monkeypatch, tmp_path):
    doc = pdf(tmp_path)

    def edit(command, check):
        path = Path(command[-1])
        text = path.read_text()
        text = text.replace("name: \n", "name: Plan\n").replace("doc: \n", f"doc: {doc}\n")
        path.write_text(text + "<p>One.</p>\n\n<p>Two.</p>\n")

    monkeypatch.setattr(assignment_module.subprocess, "run", edit)
    personal.get(f"{COURSE}/assignments", json=[])
    personal.post(f"{COURSE}/assignments", json=assignment(11, "Plan"))
    in_module(personal, [{}])
    personal.put(f"{COURSE}/assignments/11", json={})
    uploads(personal, COURSE, 11, [99])

    run("assignment")

    created = body(calls(personal, "POST", f"{COURSE}/assignments")[0])["assignment"]
    assert created["name"] == "Plan"
    assert created["description"] == "<p>One.</p>\n\n<p>Two.</p>"
    assert calls(personal, "POST", f"{COURSE}/assignments/11/submissions")


def test_rubric_by_title_attaches_the_course_rubric(personal, capsys):
    personal.get(f"{COURSE}/rubrics", json=[{"id": 90, "title": "Some Rubric"}])
    personal.get(f"{COURSE}/assignments", json=[assignment(11, "Plan")])
    in_module(personal, [{}])
    personal.post(f"{API}/courses/7/rubric_associations", json={})

    run("assignment", "--name", "Plan", "--rubric", "Some Rubric")

    association = body(calls(personal, "POST", f"{COURSE}/rubric_associations")[0])
    assert association["rubric_association"] == {
        "rubric_id": 90,
        "association_type": "Assignment",
        "association_id": 11,
        "purpose": "grading",
        "use_for_grading": False,
    }
    assert not calls(personal, "POST", f"{COURSE}/rubrics")
    assert "Attaching rubric: Some Rubric" in capsys.readouterr().out
