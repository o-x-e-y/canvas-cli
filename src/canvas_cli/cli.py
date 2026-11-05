import argparse
import sys

from canvas_cli import announcements, assignment, courses, deadlines, feedback, outcomes
from canvas_cli.api import Error


def add_course(parser, help):
    # SUPPRESS rather than a default, here and on the root parser: a subparser
    # copies every attribute it has onto the namespace, so a default of None
    # would wipe out a -c given before the subcommand. The default course is
    # chosen after parsing, per subcommand.
    parser.add_argument("-c", "--course", default=argparse.SUPPRESS, help=help)


COURSE_HELP = "a nickname from the settings, a course id, or the course's full name"


def parser():
    root = argparse.ArgumentParser(
        prog="canvas",
        description="Your own work on Canvas: proof-of-work assignments, hand-ins, your "
        "standing per learning outcome, deadlines, announcements and new feedback. "
        "Settings live in ~/.config/canvas/settings.json; -c picks a course, and without it "
        "a command uses its default from the settings.",
    )
    add_course(root, COURSE_HELP)
    commands = root.add_subparsers(title="commands", required=True, metavar="COMMAND")

    create = commands.add_parser(
        "assignment",
        help="create or continue an assignment in a course you teach",
        description="Create an assignment, or continue the one with the same name: add what "
        "it is missing and submit --doc as a new attempt. It goes into the course's module "
        "from the settings, else its first module. Without --name, opens the editor from "
        "the settings, or $EDITOR, for a form.",
    )
    add_course(create, COURSE_HELP)
    create.add_argument("--name", help="assignment title")
    create.add_argument("--desc", default="", help="description, as HTML")
    create.add_argument(
        "--rubric",
        help="the title of one of the course's rubrics, or comma-separated learning outcomes "
        "by title or id, one criterion each, e.g. Analysis-S2,PL-1",
    )
    create.add_argument(
        "--doc",
        action="append",
        default=[],
        help="file to upload and submit; repeat for more files. Publishes the assignment",
    )
    create.add_argument(
        "--publish", action="store_true", help="publish the assignment without submitting anything"
    )
    create.add_argument(
        "--indent",
        type=int,
        help="indent of the module item; default from the course's settings, else 0",
    )
    create.add_argument(
        "--after",
        metavar="HEADER",
        help="place it at the end of the group under this module header, instead of at the "
        "end of the module",
    )
    create.set_defaults(run=assignment.run)

    hand_in = commands.add_parser(
        "hand-in",
        help="hand in to an existing assignment",
        description="Hand files, a URL or text in to an existing assignment. A course name "
        "that repeats across semesters means the newest one.",
    )
    add_course(hand_in, COURSE_HELP)
    hand_in.add_argument("--name", required=True, help="the assignment's exact name")
    what = hand_in.add_mutually_exclusive_group(required=True)
    what.add_argument(
        "--doc", action="append", help="file to upload and submit; repeat for more files"
    )
    what.add_argument("--url", help="a link, for assignments that take a website URL")
    what.add_argument("--text", help="HTML, for assignments that take a text entry")
    hand_in.set_defaults(run=assignment.run_hand_in)

    delete = commands.add_parser(
        "delete",
        help="delete an assignment",
        description="Delete an assignment, with any submission on it. It asks first, unless "
        "given --yes. It can be restored from the course's undelete page, which is printed.",
    )
    add_course(delete, COURSE_HELP)
    delete.add_argument("assignment", metavar="ID_OR_NAME")
    delete.add_argument("-y", "--yes", action="store_true", help="delete without asking")
    delete.set_defaults(run=assignment.run_delete)

    standing = commands.add_parser(
        "outcomes",
        help="your score per learning outcome and the work behind it",
        description="Show the current score on each learning outcome in a course and the "
        "assignments behind it: assessed ones with their score, '-' for a criterion left "
        "unrated, and '?' for ones whose rubric claims the outcome but that are not assessed "
        "yet.",
    )
    add_course(standing, COURSE_HELP)
    standing.set_defaults(run=outcomes.run)

    news = commands.add_parser(
        "feedback",
        help="feedback on your submissions that is new since the last run",
        description="Print feedback on your submissions that is new since the last run: "
        "comments from others and assessments, in every course that is still running, or "
        "only the one -c names.",
    )
    add_course(news, COURSE_HELP)
    news.add_argument("--notify", action="store_true", help="also show each one as a notification")
    news.set_defaults(run=feedback.run)

    due = commands.add_parser(
        "deadlines",
        help="what is due soon, and what is past due and missing",
        description="List what is due in the coming days across your courses, or only the "
        "one -c names, with whether you handed it in, and the assignments that are past due "
        "and missing. A hand-in, or a mark from `canvas done`, stops counting when the "
        "assignment is edited after it and before its due date: that is how a teacher reuses "
        "an assignment for the next sprint.",
    )
    add_course(due, COURSE_HELP)
    due.add_argument("--days", type=int, default=14, help="how far ahead to look (default 14)")
    due.set_defaults(run=deadlines.run)

    done = commands.add_parser(
        "done",
        help="mark an assignment done in your Canvas planner",
        description="Mark an assignment done in your own Canvas planner, the To Do checkbox "
        "on the website, so `canvas deadlines` counts it as handed in. For a hand-in that "
        "stopped counting because the teacher only fixed a typo. Nothing is submitted and "
        "the teacher sees nothing. Looks in every course that is still running, or only the "
        "one -c names.",
    )
    add_course(done, COURSE_HELP)
    done.add_argument("assignment", help="the assignment's exact name, or its id")
    done.set_defaults(run=deadlines.run_done)

    posts = commands.add_parser(
        "announcements",
        help="recent announcements, as text",
        description="Print the announcements of the past days in every course that is still "
        "running, or only the one -c names, oldest first.",
    )
    add_course(posts, COURSE_HELP)
    posts.add_argument("--days", type=int, default=14, help="how far back to look (default 14)")
    posts.add_argument(
        "--unread", action="store_true", help="only the ones you haven't read on Canvas"
    )
    posts.set_defaults(run=announcements.run)

    listing = commands.add_parser(
        "courses",
        help="your active courses, with ids, terms, roles and nicknames",
        description="List your active courses with their id, term, your roles and the "
        "nickname the settings give them, to update the settings when a semester starts.",
    )
    listing.set_defaults(run=courses.run)

    modules = commands.add_parser(
        "modules",
        help="a course's modules and their items",
        description="List a course's modules with their ids and items, indented as on "
        "Canvas, and mark the one new assignments go into.",
    )
    add_course(modules, COURSE_HELP)
    modules.set_defaults(run=courses.run_modules)

    return root


def main(argv=None):
    args = parser().parse_args(argv)
    args.course = getattr(args, "course", None)
    try:
        args.run(args)
    except Error as error:
        sys.exit(f"Error: {error}")
