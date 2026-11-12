import re
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

from canvas_cli.api import Error, api_url, get_all, local, request
from canvas_cli.courses import current_courses, label, print_courses, resolve

PARAGRAPHS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "blockquote"}
LINES = {"br": "\n", "tr": "\n", "li": "\n- "}
TOPIC = re.compile(r"/courses/(\d+)/discussion_topics/(\d+)")


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


def recent(args):
    """The names of the courses looked at, by context code, and their announcements of the
    past days. None when no course is running."""
    if args.course:
        course = resolve(args.course, "announcements")
        courses = [{"id": course.id, "name": course.name}]
    else:
        courses = current_courses()
    if not courses:
        print("No running courses.")
        return None
    print_courses([label(c["id"], c["name"]) for c in courses])
    names = {f"course_{c['id']}": c["name"] for c in courses}

    since = datetime.now(UTC) - timedelta(days=args.days)
    posts = get_all(
        "/announcements",
        per_page=100,
        start_date=since.date().isoformat(),
        **{"context_codes[]": list(names)},
    )
    return names, sorted(posts, key=lambda p: p["posted_at"] or "")


def run(args):
    found = recent(args)
    if found is None:
        return
    names, posts = found
    if args.unread:
        posts = [post for post in posts if post.get("read_state") == "unread"]
    if not posts:
        print(f"No {'unread ' if args.unread else ''}announcements in the past {args.days} days.")

    for post in posts:
        posted = local(post["posted_at"]).strftime("%a %d %b %H:%M")
        unread = "  (unread)" if post.get("read_state") == "unread" else ""
        print(f"## {names.get(post['context_code'], '')}: {post['title']}{unread}")
        print(f"{posted}, {post.get('user_name') or ''}\n{post['html_url']}\n")
        print(text(post["message"]) + "\n")


def mark_read(course_id, topic_id):
    # Answers 204 without a body
    request("PUT", f"{api_url()}/courses/{course_id}/discussion_topics/{topic_id}/read")


def run_mark_read(args):
    if bool(args.urls) == args.all:
        raise Error("Give the URLs of the announcements to mark as read, or --all.")

    if args.urls:
        topics = [(url, TOPIC.search(url)) for url in args.urls]
        wrong = [url for url, match in topics if not match]
        if wrong:
            raise Error(f"Not an announcement's URL: {', '.join(wrong)}")
        for url, match in topics:
            mark_read(*match.groups())
            print(f"Marked as read: {url}")
        return

    found = recent(args)
    if found is None:
        return
    names, posts = found
    unread = [post for post in posts if post.get("read_state") == "unread"]
    if not unread:
        print(f"No unread announcements in the past {args.days} days.")
    newest = datetime.now(UTC) - timedelta(minutes=args.min_age)
    for post in unread:
        what = f"{names.get(post['context_code'], '')}: {post['title']}"
        if post["posted_at"] and local(post["posted_at"]) > newest:
            print(f"Left unread, posted in the past {args.min_age:g} minutes: {what}")
            continue
        mark_read(post["context_code"].removeprefix("course_"), post["id"])
        print(f"Marked as read: {what}")
