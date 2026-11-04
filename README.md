# canvas-cli

A command-line tool for a student's own work on Canvas LMS, built around a
*personal course*: a course where you are the teacher, so you can create
assignments as proof of work, attach rubrics linked to learning outcomes, and
hand your documents in to them.

| command | |
|---|---|
| `canvas assignment --name <n> [--desc <html>] [--rubric <outcomes>] [--doc <file>] [--publish]` | create an assignment in the personal course, or continue the one with that name, and optionally hand a file in |
| `canvas hand-in --course <course> --name <n> --doc <file>` | hand a file in to an existing assignment in another course |
| `canvas delete <id or name>` | delete an assignment from the personal course |
| `canvas outcomes` | the current score on each learning outcome, the assessed work behind it, and work that claims an outcome but is not assessed yet |
| `canvas feedback [--notify]` | comments and assessments on your submissions that are new since the last run |

The personal course is the one you teach whose name ends in "personal course",
and new assignments go into its first module.

## Settings

`~/.config/canvas/settings.json`:

```json
{
  "url": "https://school.instructure.com",
  "api_key_file": "/run/secrets/canvas-api-key",
  "editor": "codium --wait"
}
```

The access token comes from Account, Settings, New access token. `editor` is
optional and falls back to `$EDITOR`; `canvas assignment` without `--name`
opens it for a form.

## Nix

The flake exports `overlays.default` and a home-manager module:

```nix
programs.canvas = {
  enable = true;
  url = "https://school.instructure.com";
  apiKeyFile = "/run/secrets/canvas-api-key";
  feedback.enable = true; # hourly desktop notification
};
```
