import os
import re
import shlex
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

from canvas_cli.api import Error, base_url, delete, get, get_all, post, put, settings, upload
from canvas_cli.courses import module_items, resolve, target_module

TEMPLATE = """\
# New Canvas assignment. Fill in the fields, write the description as HTML
# below the --- line, then save and close the editor. Lines starting with #
# are ignored here; leave a field empty to skip it. doc takes one or more
# paths, separated by commas.
name: {name}
rubric: {rubric}
doc: {doc}
---
{desc}"""


def from_editor(args):
    with tempfile.NamedTemporaryFile("w+", prefix="canvas-assignment-", suffix=".md") as f:
        f.write(
            TEMPLATE.format(
                name=args.name or "",
                rubric=args.rubric or "",
                doc=", ".join(args.doc),
                desc=args.desc,
            )
        )
        f.flush()
        editor = settings().get("editor") or os.environ.get("EDITOR", "vi")
        subprocess.run([*shlex.split(editor), f.name], check=True)
        f.seek(0)
        text = f.read()

    header, separator, desc = text.partition("\n---\n")
    if not separator:
        raise Error("The form lost its --- line; nothing was created.")
    fields = {}
    for line in header.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, colon, value = line.partition(":")
        if not colon or key.strip() not in ("name", "rubric", "doc"):
            raise Error(f"Unknown line in the form: {line}")
        fields[key.strip()] = value.strip()
    if not fields.get("name"):
        raise Error("The form has no name; nothing was created.")
    args.name = fields["name"]
    args.rubric = fields.get("rubric") or None
    args.doc = [d.strip() for d in fields.get("doc", "").split(",") if d.strip()]
    args.desc = desc.strip()


def rubric_criteria(course, wanted):
    outcomes = {}
    for link in get_all(f"{course.url}/outcome_group_links", outcome_style="full", per_page=100):
        outcomes[link["outcome"]["id"]] = link["outcome"]
    by_title = {}
    for outcome in outcomes.values():
        by_title.setdefault(outcome["title"].strip(), []).append(outcome)

    chosen, problems = [], []
    for title in wanted:
        if title.isdigit() and int(title) in outcomes:
            chosen.append(outcomes[int(title)])
            continue
        matches = by_title.get(title, [])
        if len(matches) == 1:
            chosen.append(matches[0])
        elif matches:
            ids = ", ".join(str(o["id"]) for o in matches)
            problems.append(f"{title} matches {len(matches)} outcomes (ids: {ids}); pass the id")
        else:
            problems.append(f"{title} is not an outcome in {course.name}")
    if problems:
        raise Error("Unknown outcome(s): " + "; ".join(problems))

    criteria = {}
    for i, outcome in enumerate(chosen):
        criteria[str(i)] = {
            "description": outcome["title"].strip(),
            "long_description": re.sub(r"<link[^>]*>", "", outcome["description"] or ""),
            "points": outcome["points_possible"],
            "learning_outcome_id": outcome["id"],
            "mastery_points": outcome["mastery_points"],
            "ratings": {str(j): r for j, r in enumerate(outcome["ratings"])},
        }
    return criteria


def find_assignment(course, name):
    matches = [
        assignment
        for assignment in get_all(f"{course.url}/assignments", per_page=100)
        if assignment["name"] == name
    ]
    if len(matches) > 1:
        ids = ", ".join(str(a["id"]) for a in matches)
        raise Error(
            f'{len(matches)} assignments are named "{name}" (ids: {ids}). '
            "Delete or rename the extras first."
        )
    return matches[0] if matches else None


def files(docs):
    paths = [Path(doc).expanduser() for doc in docs]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise Error("No such file: " + ", ".join(missing))
    return paths


def submit(course, assignment_id, docs=(), url=None, text=None):
    submissions = f"{course.url}/assignments/{assignment_id}/submissions"
    if docs:
        file_ids = []
        for doc in docs:
            slot = post(f"{submissions}/self/files", {"name": doc.name, "size": doc.stat().st_size})
            file_ids.append(upload(slot["upload_url"], slot["upload_params"], doc)["id"])
        submission = {"submission_type": "online_upload", "file_ids": file_ids}
    elif url:
        submission = {"submission_type": "online_url", "url": url}
    else:
        submission = {"submission_type": "online_text_entry", "body": text}
    post(submissions, {"submission": submission})


@contextmanager
def step(doing):
    try:
        yield
    except Error as error:
        raise Error(
            f"{error}\nThat was while {doing}; the steps before it are done. Rerun the "
            "same command to continue from there."
        ) from None


def position_after(course, module, header):
    items = sorted(module_items(course, module), key=lambda item: item["position"])
    heads = [i for i in items if i["type"] == "SubHeader" and i["title"].strip() == header]
    if not heads:
        names = "\n  ".join(i["title"] for i in items if i["type"] == "SubHeader")
        raise Error(f'{module["name"]} has no header "{header}". Its headers:\n  {names}')
    head = heads[0]
    last = head
    for item in items[items.index(head) + 1 :]:
        if item["indent"] <= head["indent"]:
            break
        last = item
    return last["position"] + 1


def run_delete(args):
    course = resolve(args.course, "delete")
    wanted = args.assignment
    if wanted.isdigit():
        assignment = get(f"{course.url}/assignments/{wanted}")
    else:
        assignment = find_assignment(course, wanted)
        if not assignment:
            raise Error(f'{course.name} has no assignment named "{wanted}".')
    label = f'"{assignment["name"]}" (id: {assignment["id"]}) from {course.name}'
    if not args.yes:
        if not sys.stdin.isatty():
            raise Error(f"Pass --yes to delete {label} without asking.")
        answer = input(f"Delete {label}, with any submissions on it? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing deleted.")
            return
    delete(f"{course.url}/assignments/{assignment['id']}")
    print(f"Deleted {label}. Restore it at {base_url()}{course.url}/undelete")


SUBMISSION_TYPES = {"doc": "online_upload", "url": "online_url", "text": "online_text_entry"}


def run_hand_in(args):
    docs = files(args.doc or [])
    course = resolve(args.course, "hand-in")
    assignment = find_assignment(course, args.name)
    if not assignment:
        names = "\n  ".join(a["name"] for a in get_all(f"{course.url}/assignments", per_page=100))
        raise Error(
            f'{course.name} has no assignment named "{args.name}". Its assignments:\n  {names}'
        )
    kind = "doc" if docs else "url" if args.url else "text"
    if SUBMISSION_TYPES[kind] not in assignment["submission_types"]:
        types = ", ".join(assignment["submission_types"])
        raise Error(f'"{args.name}" takes {types}, not {SUBMISSION_TYPES[kind]}.')

    print(f"Handing in to {course.name}: {args.name}")
    submit(course, assignment["id"], docs, args.url, args.text)
    print("Submitted!")


def run(args):
    if not args.name:
        from_editor(args)
    docs = files(args.doc)
    publish = args.publish or bool(docs)
    course = resolve(args.course, "assignment")

    criteria = None
    if args.rubric:
        criteria = rubric_criteria(course, [title.strip() for title in args.rubric.split(",")])

    assignment = find_assignment(course, args.name)
    if assignment:
        print(f"Found existing assignment: {args.name} (id: {assignment['id']})")
        if args.desc and args.desc != assignment["description"]:
            with step("updating the description"):
                put(
                    f"{course.url}/assignments/{assignment['id']}",
                    {"assignment": {"description": args.desc}},
                )
            print("Description updated.")
    else:
        print(f"Creating assignment: {args.name}")
        assignment = post(
            f"{course.url}/assignments",
            {
                "assignment": {
                    "name": args.name,
                    "description": args.desc,
                    "submission_types": ["online_upload"],
                    "published": publish,
                }
            },
        )
        print(f"Assignment created (id: {assignment['id']}).")
    assignment_id = assignment["id"]

    with step("adding it to a module"):
        in_module = get(
            f"{course.url}/module_item_sequence", asset_type="Assignment", asset_id=assignment_id
        )["items"]
        if in_module:
            if args.after or args.indent is not None:
                print("It is already in a module; --after and --indent only apply when adding it.")
        else:
            module = target_module(course)
            item = {
                "type": "Assignment",
                "content_id": assignment_id,
                "indent": course.indent if args.indent is None else args.indent,
            }
            if args.after:
                item["position"] = position_after(course, module, args.after)
            print(f"Adding to module {module['name']}...")
            post(f"{course.url}/modules/{module['id']}/items", {"module_item": item})
            print("Added to module.")

    if criteria and assignment.get("rubric"):
        print("The assignment already has a rubric; leaving it as is.")
    elif criteria:
        print(f"Adding rubric: {args.rubric}")
        with step("adding the rubric"):
            post(
                f"{course.url}/rubrics",
                {
                    "rubric": {"title": args.name, "criteria": criteria},
                    "rubric_association": {
                        "association_type": "Assignment",
                        "association_id": assignment_id,
                        "purpose": "grading",
                        "use_for_grading": False,
                    },
                },
            )
        print("Rubric added.")

    if publish and not assignment["published"]:
        with step("publishing it"):
            put(f"{course.url}/assignments/{assignment_id}", {"assignment": {"published": True}})
        print("Assignment published.")

    if docs:
        print("Uploading and submitting: " + ", ".join(str(doc) for doc in docs))
        with step("submitting the files"):
            submit(course, assignment_id, docs)
        print("Submitted!")
