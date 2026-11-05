# canvas-cli

A command-line tool for a student's own work on Canvas LMS: create assignments
as proof of work in a course you teach (such as a personal course), attach
rubrics, hand documents in, and keep track of your
standing per outcome, deadlines, announcements and new feedback.

| command | |
|---|---|
| `canvas assignment --name <n> [--desc <html>] [--rubric <outcomes>] [--doc <file>]... [--publish] [--indent N] [--after <header>]` | create an assignment, or continue the one with that name, and optionally hand files in |
| `canvas hand-in --name <n> (--doc <file>... \| --url <url> \| --text <html>)` | hand in to an existing assignment |
| `canvas delete <id or name> [--yes]` | delete an assignment; asks first |
| `canvas outcomes` | the current score on each learning outcome, the assessed work behind it, and work that claims an outcome but is not assessed yet |
| `canvas feedback [--notify]` | comments and assessments on your submissions that are new since the last run |
| `canvas deadlines [--days N]` | what is due soon, and what is past due and missing |
| `canvas announcements [--days N] [--unread]` | recent announcements as text |
| `canvas courses` | your active courses with ids, terms, roles and nicknames |
| `canvas modules` | a course's modules and items, and where new assignments go |

Every command but `courses` takes `-c COURSE`, before or after the
subcommand: a nickname from the settings, a course id, or the course's full
name (a name that repeats across semesters means the newest). Without `-c` a
command uses its default from the settings; `feedback`, `deadlines` and
`announcements` cover every running course instead.

What you may do in a course is up to Canvas: when it refuses, the error says
so and passes on its message.

## Settings

`~/.config/canvas/settings.json`:

```json
{
  "url": "https://school.instructure.com",
  "api_key_file": "/run/secrets/canvas-api-key",
  "editor": "codium --wait",
  "courses": {
    "personal": { "id": 12345, "indent": 1 },
    "general": { "id": 23456 }
  },
  "defaults": { "assignment": "personal", "outcomes": "personal", "hand-in": "general" }
}
```

- `api_key_file` holds an access token, from Account, Settings, New access token.
- `editor` is optional and falls back to `$EDITOR`; `canvas assignment` without
  `--name` opens it for a form.
- A course's `module` (an id) is where new assignments go; without it, the
  course's first module. `indent` is the default indent of new module items,
  else 0.
- When a semester starts, `canvas courses` shows the new course ids, and
  commands warn when a nickname points at a course that has ended.

`--rubric` takes the title of a rubric the course already has, which is
attached as it is, or a list of the course's learning outcomes by title or id,
which becomes a new rubric with one criterion per outcome. Outcomes have to be
imported into the course first.

## Install

With pip or pipx, from a checkout:

    pipx install .

With Nix, the flake exports a package, `overlays.default` and a home-manager
module:

```nix
programs.canvas = {
  enable = true;
  url = "https://school.instructure.com";
  apiKeyFile = "/run/secrets/canvas-api-key";
  courses.personal = { id = 12345; indent = 1; };
  defaults.assignment = "personal";
  feedback.enable = true; # hourly desktop notification
};
```
