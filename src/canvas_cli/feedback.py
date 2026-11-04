import json
import os
import subprocess
from pathlib import Path

from canvas_cli.api import get, get_all
from canvas_cli.courses import current_courses, resolve

STATE_HOME = os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")
STATE_PATH = Path(STATE_HOME, "canvas-feedback.json")


def assessment(submission):
    assignment = submission["assignment"]
    lines = []
    if submission["grade"]:
        lines.append(f"Grade: {submission['grade']}")
    criteria = {c["id"]: c for c in assignment.get("rubric", [])}
    for criterion_id, rated in (submission.get("rubric_assessment") or {}).items():
        criterion = criteria.get(criterion_id)
        if not criterion:
            continue
        ratings = {r["id"]: r["description"] for r in criterion["ratings"]}
        # Unrated criteria still carry a rating_id, just no points
        if rated.get("points") is None:
            rating = "not rated"
        else:
            rating = ratings.get(rated.get("rating_id"), f"{rated['points']:g} points")
        line = f"{criterion['description'].strip()}: {rating}"
        if rated.get("comments"):
            line += f" ({rated['comments']})"
        lines.append(line)
    return "\n".join(lines)


def feedback(me, courses):
    for course in courses:
        submissions = get_all(
            f"/courses/{course['id']}/students/submissions",
            per_page=100,
            **{
                "student_ids[]": "self",
                "include[]": ["submission_comments", "rubric_assessment", "assignment"],
            },
        )
        for submission in submissions:
            title = f"{course['name']}: {submission['assignment']['name']}"
            for comment in submission.get("submission_comments", []):
                if comment["author_id"] != me:
                    yield (
                        f"comment:{comment['id']}",
                        title,
                        f"{comment['author_name']}: {comment['comment']}",
                    )
            if submission["graded_at"]:
                yield (
                    f"assessed:{submission['id']}:{submission['graded_at']}",
                    title,
                    "Assessed\n" + assessment(submission),
                )


def run(args):
    if args.course:
        course = resolve(args.course, "feedback")
        courses = [{"id": course.id, "name": course.name}]
    else:
        courses = current_courses(enrollment_type="student")
    seen = set(json.loads(STATE_PATH.read_text())) if STATE_PATH.exists() else None
    items = list(feedback(get("/users/self")["id"], courses))

    if seen is None:
        print(f"First run: recorded {len(items)} existing items; later runs report what is new.")
    else:
        for key, title, body in items:
            if key in seen:
                continue
            print(f"{title}\n{body}\n")
            if args.notify:
                subprocess.run(["notify-send", "--app-name=Canvas", title, body], check=False)

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    keys = {key for key, _, _ in items}
    if args.course and seen:
        # Only one course was checked; keep what the others have seen
        keys |= seen
    STATE_PATH.write_text(json.dumps(sorted(keys)))
