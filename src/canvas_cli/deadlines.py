from datetime import UTC, datetime, timedelta
from itertools import groupby

from canvas_cli.api import Error, get_all, local, post, put
from canvas_cli.courses import current_courses, label, print_courses, resolve

KINDS = {"assignment": "", "quiz": "quiz", "discussion_topic": "discussion"}


def parse(timestamp):
    return datetime.fromisoformat(timestamp) if timestamp else None


def counts(at, assignment):
    """Whether a hand-in or a planner mark made at this time still counts. A teacher who
    reuses an assignment moves its due date forward, and Canvas keeps the hand-in for
    the old one; the only trace is an edit after the hand-in and before the due date."""
    if not at:
        return False
    edited, due = parse(assignment["updated_at"]), parse(assignment["due_at"])
    return not (parse(at) < edited and (due is None or edited < due))


def overrides():
    return [
        o
        for o in get_all("/planner/overrides", per_page=100)
        if o["plannable_type"] == "assignment" and not o.get("deleted_at")
    ]


def marks():
    """When you marked each assignment done in the Canvas planner."""
    return {o["plannable_id"]: o["updated_at"] for o in overrides() if o["marked_complete"]}


def handed_in(assignment, marked):
    submission = assignment.get("submission") or {}
    if counts(submission.get("submitted_at"), assignment):
        return "submitted"
    if counts(marked.get(assignment["id"]), assignment):
        return "marked done"
    return None


def status(item, assignment, marked):
    submissions = item.get("submissions") or {}
    states = ("graded", "submitted", "excused", "missing", "late")
    if assignment:
        how = handed_in(assignment, marked)
        if how == "marked done":
            return how
        if how is None:
            states = ("excused", "missing", "late")
    return next((state for state in states if submissions.get(state)), "")


def describe(item, assignment, marked):
    plannable = item["plannable"]
    title = plannable.get("title") or plannable.get("name") or ""
    kind = KINDS.get(item["plannable_type"], item["plannable_type"].replace("_", " "))
    notes = ", ".join(note for note in (kind, status(item, assignment, marked)) if note)
    line = f"{item.get('context_name') or 'Personal'}: {title}"
    return f"{line}  ({notes})" if notes else line


def scope(args, command):
    if args.course:
        course = resolve(args.course, command)
        return [{"id": course.id, "name": course.name}]
    return current_courses(enrollment_type="student")


def past_due(course_id, assignments, marked, now):
    """Canvas's missing submissions, and the past-due assignments whose only hand-in
    no longer counts, minus what counts as handed in."""
    missing = get_all("/users/self/missing_submissions", per_page=100, **{"include[]": "course"})
    if course_id:
        missing = [a for a in missing if a["course_id"] == course_id]
    rows = [(a["course"]["name"], a) for a in missing if not handed_in(a, marked)]
    listed = {a["id"] for a in missing}
    for name, assignment in assignments.values():
        submission = assignment.get("submission") or {}
        if (
            assignment["id"] not in listed
            and assignment["due_at"]
            and parse(assignment["due_at"]) < now
            and submission.get("submitted_at")
            and not submission.get("excused")
            and not handed_in(assignment, marked)
        ):
            rows.append((name, assignment))
    return sorted(rows, key=lambda row: row[1]["due_at"] or "")


def run(args):
    now = datetime.now(UTC)
    params = {
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=args.days)).isoformat(),
        "per_page": 100,
    }
    courses = scope(args, "deadlines")
    course_id = courses[0]["id"] if args.course else None
    if course_id:
        params["context_codes[]"] = f"course_{course_id}"
        print_courses([label(course_id, courses[0]["name"])])
    else:
        print("Courses: all you're enrolled in\n")
    items = sorted(get_all("/planner/items", **params), key=lambda i: i["plannable_date"])
    assignments = {
        assignment["id"]: (course["name"], assignment)
        for course in courses
        for assignment in get_all(
            f"/users/self/courses/{course['id']}/assignments",
            per_page=100,
            **{"include[]": "submission"},
        )
    }
    marked = marks()

    missing = past_due(course_id, assignments, marked, now)
    if missing:
        print("Past due and missing")
        for name, assignment in missing:
            due = (
                local(assignment["due_at"]).strftime("%a %d %b %H:%M")
                if assignment["due_at"]
                else ""
            )
            print(f"  {due:16}  {name}: {assignment['name']}")
        print()

    if not items:
        print(f"Nothing due in the next {args.days} days.")
    for day, group in groupby(items, key=lambda i: local(i["plannable_date"]).date()):
        print(day.strftime("%a %d %b"))
        for item in group:
            when = local(item["plannable_date"]).strftime("%H:%M")
            found = None
            if item["plannable_type"] == "assignment":
                found = assignments.get(item["plannable"].get("id"))
            print(f"  {when}  {describe(item, found and found[1], marked)}")


def run_done(args):
    courses = scope(args, "done")
    wanted = args.assignment
    matches = [
        (course, assignment)
        for course in courses
        for assignment in get_all(f"/courses/{course['id']}/assignments", per_page=100)
        if assignment["name"] == wanted or str(assignment["id"]) == wanted
    ]
    labels = [label(c["id"], c["name"]) for c in courses]
    if not matches:
        raise Error(f'No assignment named "{wanted}" in {", ".join(labels)}.')
    if len(matches) > 1:
        found = "\n  ".join(
            f"{label(c['id'], c['name'])}: {a['name']} (id: {a['id']})" for c, a in matches
        )
        raise Error(f'More than one assignment is "{wanted}"; pass its id:\n  {found}')
    course, assignment = matches[0]
    what = f"{label(course['id'], course['name'])}: {assignment['name']}"

    existing = next((o for o in overrides() if o["plannable_id"] == assignment["id"]), None)
    if existing is None:
        post(
            "/planner/overrides",
            {
                "plannable_type": "assignment",
                "plannable_id": assignment["id"],
                "marked_complete": True,
            },
        )
    elif existing["marked_complete"] and counts(existing["updated_at"], assignment):
        print(f"Already marked done: {what}")
        return
    else:
        if existing["marked_complete"]:
            # The mark is older than the last edit. Setting it to true again changes
            # nothing, so Canvas would keep the old updated_at the rule compares.
            put(f"/planner/overrides/{existing['id']}", {"marked_complete": False})
        put(f"/planner/overrides/{existing['id']}", {"marked_complete": True})
    print(f"Marked done in your Canvas planner: {what}")
