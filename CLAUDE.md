# canvas-cli

One `canvas` command over the Canvas REST API for the user's own school work,
with subcommands; `canvas --help` lists them. The skills that drive it
(`canvas-submit`, `fontys-coach`) live in the user's nixos repo, not here;
change their text there when a subcommand, flag or output changes.

## Layout

| file | |
|---|---|
| `api.py` | settings, the session, request helpers, Link-header pagination, the personal course |
| `cli.py` | the argparse surface: every subcommand and its help text |
| `assignment.py` | `assignment` (create or continue, rubric, module, publish, submit), `hand-in`, `delete` |
| `outcomes.py` | `outcomes`: outcome rollups, results, and unassessed rubric claims |
| `feedback.py` | `feedback`: new comments and assessments, state in `$XDG_STATE_HOME/canvas-feedback.json` |
| `nix/hm-module.nix` | writes `~/.config/canvas/settings.json` and the feedback timer |

## Working on it

`nix develop`, then `pytest` and `ruff check`. The suite is offline:
`responses` serves hand-written payloads, so no test touches a real course.
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
