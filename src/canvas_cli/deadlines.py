from datetime import UTC, datetime, timedelta
from itertools import groupby
from operator import itemgetter

from canvas_cli.api import get_all, local
from canvas_cli.courses import resolve

KINDS = {"assignment": "", "quiz": "quiz", "discussion_topic": "discussion"}


def status(item, stale):
    submissions = item.get("submissions") or {}
    for state in ("graded", "submitted", "excused", "missing", "late"):
        if stale and state in ("graded", "submitted"):
            continue
        if submissions.get(state):
            return state
    return ""


def stale_submissions(items):
    """Assignments handed in before their last edit, such as one reused every sprint
    with a new due date: Canvas still counts the hand-in for the old one."""
    submitted = sorted(
        (item["course_id"], item["plannable"]["id"])
        for item in items
        if item["plannable_type"] == "assignment"
        and (item.get("submissions") or {}).get("submitted")
    )
    stale = set()
    for course_id, group in groupby(submitted, key=itemgetter(0)):
        assignments = get_all(
            f"/users/self/courses/{course_id}/assignments",
            per_page=100,
            **{
                "assignment_ids[]": [assignment_id for _, assignment_id in group],
                "include[]": "submission",
            },
        )
        for assignment in assignments:
            submitted_at = (assignment.get("submission") or {}).get("submitted_at")
            if submitted_at and datetime.fromisoformat(submitted_at) < datetime.fromisoformat(
                assignment["updated_at"]
            ):
                stale.add(assignment["id"])
    return stale


def describe(item, stale):
    plannable = item["plannable"]
    title = plannable.get("title") or plannable.get("name") or ""
    kind = KINDS.get(item["plannable_type"], item["plannable_type"].replace("_", " "))
    notes = ", ".join(note for note in (kind, status(item, stale)) if note)
    line = f"{item.get('context_name') or 'Personal'}: {title}"
    return f"{line}  ({notes})" if notes else line


def run(args):
    now = datetime.now(UTC)
    params = {
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=args.days)).isoformat(),
        "per_page": 100,
    }
    course = resolve(args.course, "deadlines") if args.course else None
    if course:
        params["context_codes[]"] = f"course_{course.id}"
    items = sorted(get_all("/planner/items", **params), key=lambda i: i["plannable_date"])
    stale = stale_submissions(items)

    missing = get_all("/users/self/missing_submissions", per_page=100, **{"include[]": "course"})
    if course:
        missing = [m for m in missing if m["course_id"] == course.id]
    if missing:
        print("Past due and missing")
        for assignment in sorted(missing, key=lambda a: a["due_at"] or ""):
            due = (
                local(assignment["due_at"]).strftime("%a %d %b %H:%M")
                if assignment["due_at"]
                else ""
            )
            print(f"  {due:16}  {assignment['course']['name']}: {assignment['name']}")
        print()

    if not items:
        print(f"Nothing due in the next {args.days} days.")
    for day, group in groupby(items, key=lambda i: local(i["plannable_date"]).date()):
        print(day.strftime("%a %d %b"))
        for item in group:
            when = local(item["plannable_date"]).strftime("%H:%M")
            print(f"  {when}  {describe(item, item['plannable'].get('id') in stale)}")
