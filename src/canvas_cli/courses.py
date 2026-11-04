import sys
from dataclasses import dataclass
from datetime import UTC, datetime

from canvas_cli.api import Error, get, get_all, local_date, settings


@dataclass
class Course:
    id: int
    name: str
    nickname: str | None = None
    module: int | None = None
    indent: int = 0

    @property
    def url(self):
        return f"/courses/{self.id}"


def configured():
    return settings().get("courses", {})


def end(course):
    """When the course ends for you, or None when it has no end date."""
    if course.get("restrict_enrollments_to_course_dates") and course.get("end_at"):
        return course["end_at"]
    return (course.get("term") or {}).get("end_at")


def ended(course):
    end_at = end(course)
    return bool(end_at) and datetime.fromisoformat(end_at) < datetime.now(UTC)


def active_courses(**params):
    return get_all(
        "/courses", enrollment_state="active", per_page=100, **{"include[]": "term"}, **params
    )


def current_courses(**params):
    return [course for course in active_courses(**params) if not ended(course)]


def nickname_hint():
    names = ", ".join(configured()) or "none yet"
    return f"Nicknames in the settings: {names}. `canvas courses` lists your courses."


def resolve(wanted, command):
    """The course -c names, or the settings' default for this command."""
    if wanted is None:
        wanted = settings().get("defaults", {}).get(command)
        if wanted is None:
            raise Error(
                f"canvas {command} needs -c COURSE: the settings have no default course "
                f"for it. {nickname_hint()}"
            )

    if wanted in configured():
        course = get(f"/courses/{configured()[wanted]['id']}", **{"include[]": "term"})
    elif wanted.isdigit():
        course = get(f"/courses/{wanted}", **{"include[]": "term"})
    else:
        courses = active_courses()
        matches = [c for c in courses if c["name"] == wanted]
        if not matches:
            names = "\n  ".join(sorted({c["name"] for c in courses}))
            raise Error(
                f'No course nicknamed or named "{wanted}". {nickname_hint()} '
                f"Your active courses:\n  {names}"
            )
        # Course names repeat every semester, so take the newest term
        course = max(matches, key=lambda c: (c.get("term") or {}).get("start_at") or "")

    nickname = next((n for n, e in configured().items() if e["id"] == course["id"]), None)
    entry = configured().get(nickname, {})
    if ended(course):
        label = f"{nickname} ({course['name']})" if nickname else course["name"]
        print(
            f"Warning: {label} ended on {local_date(end(course))}. If a new semester has "
            "started, point the nickname at its course; `canvas courses` lists them.",
            file=sys.stderr,
        )
    return Course(
        id=course["id"],
        name=course["name"],
        nickname=nickname,
        module=entry.get("module"),
        indent=entry.get("indent", 0),
    )


def roles(course):
    seen = []
    for enrollment in course.get("enrollments", []):
        role = enrollment["type"].removesuffix("enrollment")
        if role not in seen:
            seen.append(role)
    return ", ".join(seen)


def run(args):
    courses = active_courses()
    nicknames = {entry["id"]: name for name, entry in configured().items()}
    rows = []
    for course in sorted(courses, key=lambda c: (ended(c), c["name"])):
        term = (course.get("term") or {}).get("name") or ""
        end_at = end(course)
        if end_at:
            term += f", {'ended' if ended(course) else 'ends'} {local_date(end_at)}"
        rows.append(
            (
                nicknames.get(course["id"], ""),
                str(course["id"]),
                course["name"],
                term,
                roles(course),
            )
        )
    active_ids = {course["id"] for course in courses}
    for course_id, nickname in nicknames.items():
        if course_id not in active_ids:
            rows.append((nickname, str(course_id), "(not one of your active courses)", "", ""))

    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    for row in rows:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=False)]
        print("  ".join([*cells, row[4]]).rstrip())

    defaults = settings().get("defaults", {})
    if defaults:
        print("\nDefaults: " + ", ".join(f"{cmd} → {name}" for cmd, name in defaults.items()))


def module_items(course, module):
    if "items" in module:
        return module["items"]
    return get_all(f"{course.url}/modules/{module['id']}/items", per_page=100)


def target_module(course, modules=None):
    """The module new assignments go into: the configured one, else the first."""
    if course.module:
        return get(f"{course.url}/modules/{course.module}")
    modules = modules if modules is not None else get_all(f"{course.url}/modules", per_page=100)
    if not modules:
        raise Error(f"{course.name} has no modules to add the assignment to.")
    return modules[0]


def run_modules(args):
    course = resolve(args.course, "modules")
    modules = get_all(f"{course.url}/modules", per_page=100, **{"include[]": "items"})
    target = target_module(course, modules) if modules else None
    for module in modules:
        mark = "  (new assignments go here)" if target and module["id"] == target["id"] else ""
        print(f"{module['id']}  {module['name']}{mark}")
        for item in module_items(course, module):
            print(f"  {'  ' * item['indent']}{item['title']}")
