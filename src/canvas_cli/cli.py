import argparse

from canvas_cli import assignment, feedback, outcomes


def parser():
    root = argparse.ArgumentParser(
        prog="canvas",
        description="Your own work on Canvas: proof-of-work assignments in your personal "
        "course, hand-ins elsewhere, your standing per learning outcome, and new feedback. "
        "Settings live in ~/.config/canvas/settings.json.",
    )
    commands = root.add_subparsers(title="commands", required=True, metavar="COMMAND")

    create = commands.add_parser(
        "assignment",
        help="create or continue an assignment in the personal course",
        description="Create an assignment in the personal course, or continue the one with "
        "the same name: add what it is missing and submit --doc as a new attempt. Without "
        "--name, opens the editor from the settings, or $EDITOR, for a form.",
    )
    create.add_argument("--name", help="assignment title")
    create.add_argument("--desc", default="", help="description, as HTML")
    create.add_argument("--rubric", help="comma-separated learning outcomes, e.g. Analysis-S2,PL-1")
    create.add_argument("--doc", help="file to upload and submit; publishes the assignment")
    create.add_argument(
        "--publish", action="store_true", help="publish the assignment without submitting anything"
    )
    create.set_defaults(run=assignment.run)

    hand_in = commands.add_parser(
        "hand-in",
        help="hand a file in to an existing assignment in another course",
        description="Hand a file in to an existing assignment in one of your courses. A "
        "course name that repeats across semesters means the newest one.",
    )
    hand_in.add_argument("--course", required=True, help="course name or id")
    hand_in.add_argument("--name", required=True, help="the assignment's exact name")
    hand_in.add_argument("--doc", required=True, help="file to upload and submit")
    hand_in.set_defaults(run=assignment.run_hand_in)

    delete = commands.add_parser(
        "delete",
        help="delete an assignment from the personal course",
        description="Delete an assignment from the personal course, with any submission on "
        "it. It can be restored from the course's undelete page, which is printed.",
    )
    delete.add_argument("assignment", metavar="ID_OR_NAME")
    delete.set_defaults(run=assignment.run_delete)

    standing = commands.add_parser(
        "outcomes",
        help="your score per learning outcome and the work behind it",
        description="Show the current score on each learning outcome in the personal course "
        "and the assignments behind it: assessed ones with their score, '-' for a criterion "
        "left unrated, and '?' for ones whose rubric claims the outcome but that are not "
        "assessed yet.",
    )
    standing.set_defaults(run=outcomes.run)

    news = commands.add_parser(
        "feedback",
        help="feedback on your submissions that is new since the last run",
        description="Print feedback on your submissions that is new since the last run: "
        "comments from others and assessments, in courses whose term is still running.",
    )
    news.add_argument("--notify", action="store_true", help="also show each one as a notification")
    news.set_defaults(run=feedback.run)

    return root


def main(argv=None):
    args = parser().parse_args(argv)
    args.run(args)
