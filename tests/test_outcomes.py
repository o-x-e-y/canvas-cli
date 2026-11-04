from conftest import COURSE, PERSONAL, run

ANALYSIS = {
    "id": 501,
    "title": "Analysis-S2",
    "points_possible": 4,
    "mastery_points": 3,
    "ratings": [
        {"description": "Beginning", "points": 1},
        {"description": "Proficient", "points": 3},
        {"description": "Advanced", "points": 4},
    ],
}


def result(id, assignment, score, at):
    return {
        "id": id,
        "score": score,
        "hidden": False,
        "submitted_or_assessed_at": at,
        "links": {"learning_outcome": "501", "assignment": f"assignment_{assignment}"},
    }


def test_standing_with_assessed_unrated_and_claimed_work(canvas, capsys):
    canvas.get(COURSE, json=PERSONAL)
    canvas.get(
        f"{COURSE}/outcome_results",
        json={
            "outcome_results": [
                result(1, 11, 3, "2026-10-01T10:00:00Z"),
                result(2, 12, None, "2026-10-08T10:00:00Z"),
            ],
            "linked": {
                "outcomes": [ANALYSIS],
                "alignments": [
                    {"id": "assignment_11", "name": "Research"},
                    {"id": "assignment_12", "name": "Plan"},
                ],
            },
        },
    )
    canvas.get(
        f"{COURSE}/outcome_rollups",
        json={"rollups": [{"scores": [{"links": {"outcome": "501"}, "score": 3.0}]}]},
    )
    unsubmitted = {"submitted_at": None, "grade": None}
    canvas.get(
        f"{COURSE}/assignments",
        json=[
            {"id": 11, "name": "Research", "submission": unsubmitted},
            {
                "id": 13,
                "name": "Design",
                "rubric": [{"outcome_id": 502, "description": "Design-S2 "}],
                "submission": {"submitted_at": "2026-10-20T10:00:00Z", "grade": None},
            },
            {
                "id": 14,
                "name": "Tests",
                "rubric": [{"outcome_id": 501, "description": "Analysis-S2"}],
                "submission": unsubmitted,
            },
            {
                "id": 15,
                "name": "Notes",
                "submission": {"submitted_at": "2026-10-21T10:00:00Z", "grade": None},
            },
        ],
    )

    run("outcomes")

    assert capsys.readouterr().out == (
        "Analysis-S2: 3/4 Proficient mastery\n"
        "                ?  Tests (not handed in)\n"
        "  2026-10-08    -  Plan\n"
        "  2026-10-01    3  Research\n"
        "Design-S2: not assessed yet\n"
        "  2026-10-20    ?  Design (not assessed yet)\n"
        "\n"
        "Handed in, not assessed, and no outcomes in the rubric:\n"
        "  2026-10-21  Notes\n"
    )
