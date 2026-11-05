"""Record the read-only scenarios against the live API: python tests/record.py COURSE

COURSE is any -c value for modules and outcomes, such as a nickname. Uses
your own settings and token. Review the diff before committing: nothing
personal should be left in tests/recorded.
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from recording import DIR, SCENARIOS, Scrubber, keep_fields, offline_settings, replay, run

from canvas_cli import api
from canvas_cli.courses import resolve


def record(argv, now):
    exchanges = []

    def keep(response, *args, **kwargs):
        exchanges.append(
            {
                "method": response.request.method,
                "url": response.url,
                "status": response.status_code,
                "link": response.headers.get("Link"),
                "json": response.json(),
            }
        )

    api.session().hooks["response"].append(keep)
    try:
        output = run(argv, now)
    finally:
        api.session().hooks["response"].remove(keep)
    return exchanges, output


def main():
    course = str(resolve(sys.argv[1], "record").id)
    host = api.base_url()
    key = api.settings()["api_key_file"]
    DIR.mkdir(exist_ok=True)
    for name, template in SCENARIOS.items():
        argv = [arg.format(course=course) for arg in template]
        now = datetime.now(UTC).replace(microsecond=0)
        with offline_settings(host, key):
            exchanges, live = record(argv, now)

        reduced = [{**e, "json": keep_fields(e["json"])} for e in exchanges]
        unscrubbed = {"argv": argv, "now": now.isoformat(), "exchanges": reduced}
        if replay(unscrubbed, host) != live:
            sys.exit(
                f"{name}: the kept fields don't reproduce the live output; add the missing ones"
            )

        scrubber = Scrubber(host)
        for exchange in reduced:
            scrubber.collect_ids(exchange["json"])
        recording = {
            "argv": [scrubber.string(arg) for arg in argv],
            "now": now.isoformat(),
            "exchanges": [
                {
                    **e,
                    "url": scrubber.string(e["url"]),
                    "link": e["link"] and scrubber.string(e["link"]),
                    "json": scrubber.scrub(e["json"]),
                }
                for e in reduced
            ],
        }
        (DIR / f"{name}.json").write_text(
            json.dumps(recording, indent=1, ensure_ascii=False) + "\n"
        )
        (DIR / f"{name}.out").write_text(replay(recording))
        print(f"{name}: {len(exchanges)} responses")


if __name__ == "__main__":
    main()
