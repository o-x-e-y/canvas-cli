import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

from canvas_cli.api import get_all, local
from canvas_cli.courses import current_courses, label, print_courses, resolve

PARAGRAPHS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "blockquote"}
LINES = {"br": "\n", "tr": "\n", "li": "\n- "}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in PARAGRAPHS:
            self.parts.append("\n\n")
        self.parts.append(LINES.get(tag, ""))

    def handle_endtag(self, tag):
        if tag in PARAGRAPHS:
            self.parts.append("\n\n")

    def handle_data(self, data):
        self.parts.append(re.sub(r"\s+", " ", data))


def text(html):
    parser = Text()
    parser.feed(html or "")
    lines = (line.strip() for line in "".join(parser.parts).splitlines())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def run(args):
    if args.course:
        course = resolve(args.course, "announcements")
        courses = [{"id": course.id, "name": course.name}]
    else:
        courses = current_courses()
    if not courses:
        print("No running courses.")
        return
    print_courses([label(c["id"], c["name"]) for c in courses])
    names = {f"course_{c['id']}": c["name"] for c in courses}

    since = datetime.now(UTC) - timedelta(days=args.days)
    posts = get_all(
        "/announcements",
        per_page=100,
        start_date=since.date().isoformat(),
        **{"context_codes[]": list(names)},
    )
    if args.unread:
        posts = [post for post in posts if post.get("read_state") == "unread"]
    if not posts:
        print(f"No {'unread ' if args.unread else ''}announcements in the past {args.days} days.")

    for post in sorted(posts, key=lambda p: p["posted_at"] or ""):
        posted = local(post["posted_at"]).strftime("%a %d %b %H:%M")
        unread = "  (unread)" if post.get("read_state") == "unread" else ""
        print(f"## {names.get(post['context_code'], '')}: {post['title']}{unread}")
        print(f"{posted}, {post.get('user_name') or ''}\n{post['html_url']}\n")
        print(text(post["message"]) + "\n")
