# canvas-cli

One `canvas` command over the Canvas REST API for the user's own school work,
with subcommands; `canvas --help` lists them. The skills that drive it
(`canvas-submit`, `fontys-coach`) live in the user's nixos repo, not here;
change their text there when a subcommand, flag or output changes.

## Layout

| file | |
|---|---|
| `api.py` | settings, the session, request helpers with timeouts and rate-limit retries, error messages, Link-header pagination, local dates |
| `courses.py` | `-c` resolution (nickname, id, name, per-subcommand default), course end dates, `courses`, `modules` |
| `cli.py` | the argparse surface: every subcommand and its help text |
| `assignment.py` | `assignment` (create or continue, rubric, module, publish, submit), `hand-in`, `delete` |
| `outcomes.py` | `outcomes`: outcome rollups, results, and unassessed rubric claims |
| `feedback.py` | `feedback`: new comments and assessments, state in `$XDG_STATE_HOME/canvas-feedback.json` |
| `deadlines.py` | `deadlines`: planner items and missing submissions |
| `announcements.py` | `announcements`: recent announcements, HTML to text |
| `nix/hm-module.nix` | writes `~/.config/canvas/settings.json` and the feedback timer |

## Working on it

`nix develop`, then `pytest` and `ruff check`. The suite is offline, so no
test touches a real course. `responses` serves hand-written payloads for the
edge cases, and `tests/recorded` holds real read-only responses with the
output they give. `python tests/record.py <course>` records them again: it
keeps only the fields in `FIELDS` (it stops when those don't reproduce the
live output), replaces names with placeholders, masks text and renumbers
ids. Read the diff for anything personal before committing it.
Every command that writes to Canvas changes the user's real courses, so test
against the live API only with read-only calls, or with the user's go-ahead.

Canvas traps the code already handles:

- Array parameters need `[]` in the name (`include[]`, `user_ids[]`,
  `student_ids[]`); without it Canvas silently ignores them.
- The `next` Link already carries the query string. Pagination drops `params`
  after the first page; resending them duplicates them.
- An unrated rubric criterion keeps a `rating_id` but has no `points`, so a
  rating is only real when `points` is set.
- Course names repeat every semester; pick by the newest term.
- Canvas answers 401 both for a bad token and for an action your role can't
  do; only the message tells them apart. The tool never decides what a role
  may do: it tries, and passes Canvas's refusal on.
- `-c` is defined with `default=SUPPRESS` on the root parser and on each
  subparser; a default of None on the subparser would overwrite a `-c` given
  before the subcommand. The per-subcommand default is applied after parsing.
  There is a regression test.
