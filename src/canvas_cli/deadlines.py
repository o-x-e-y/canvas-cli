from datetime import UTC, datetime, timedelta
from itertools import groupby

from canvas_cli.api import get_all, local
from canvas_cli.courses import resolve

KINDS = {"assignment": "", "quiz": "quiz", "discussion_topic": "discussion"}


def status(item):
    submissions = item.get("submissions") or {}
    for state in ("graded", "submitted", "excused", "missing", "late"):
        if submissions.get(state):
            return state
    return ""


def describe(item):
    plannable = item["plannable"]
    title = plannable.get("title") or plannable.get("name") or ""
    kind = KINDS.get(item["plannable_type"], item["plannable_type"].replace("_", " "))
    notes = ", ".join(note for note in (kind, status(item)) if note)
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
            print(f"  {local(item['plannable_date']).strftime('%H:%M')}  {describe(item)}")
