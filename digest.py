import feedparser
import smtplib
import os
import urllib.request
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import html as html_lib
import time

# Use a browser-like User-Agent so feeds don't block us
feedparser.USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 NewsDigest/1.0"
)

def fetch_feed(url):
    """Fetch an RSS feed with browser-like headers to avoid 403s."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": feedparser.USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return feedparser.parse(io.BytesIO(data))
    except Exception:
        # Fallback: let feedparser try directly
        return feedparser.parse(url)

# ── CONFIG ────────────────────────────────────────────────────────────────────
GMAIL_USER      = os.environ["GMAIL_USER"]
GMAIL_PASSWORD  = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", GMAIL_USER)

FEEDS = {
    "Economics": [
        "https://www.economist.com/finance-and-economics/rss.xml",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.imf.org/en/News/rss?language=eng",
        "https://feeds.feedburner.com/wsj/xml/rss/3_7031.xml",
        "https://feeds.feedburner.com/freakonomics/feed",
    ],
    "Environmental Policy": [
        "https://e360.yale.edu/feed",
        "https://www.carbonbrief.org/feed",
        "https://insideclimatenews.org/feed/",
        "https://www.theguardian.com/environment/rss",
        "https://grist.org/feed/",
    ],
    "College Admissions": [
        "https://www.insidehighered.com/rss.xml",
        "https://www.chronicle.com/feeds/news",
        "https://blog.collegevine.com/feed/",
        "https://blog.prepscholar.com/rss.xml",
    ],
}

# How many stories to pull per category
STORIES_PER_CATEGORY = {
    "Economics":          2,
    "Environmental Policy": 2,
    "College Admissions": 1,
}

CATEGORY_COLORS = {
    "Economics":            {"bg": "#E6F1FB", "accent": "#185FA5", "label": "#0C447C"},
    "Environmental Policy": {"bg": "#EAF3DE", "accent": "#3B6D11", "label": "#27500A"},
    "College Admissions":   {"bg": "#EEEDFE", "accent": "#534AB7", "label": "#3C3489"},
}

CATEGORY_ICONS = {
    "Economics":            "📈",
    "Environmental Policy": "🌱",
    "College Admissions":   "🎓",
}

# ── RSS FETCHING ──────────────────────────────────────────────────────────────
def fetch_top_stories(feed_urls, n):
    """Fetch the n most recent unique stories from a list of RSS feed URLs."""
    entries = []
    seen_titles = set()

    for url in feed_urls:
        try:
            feed = fetch_feed(url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()
                if not title or title.lower() in seen_titles:
                    continue
                seen_titles.add(title.lower())

                # Get summary — strip HTML tags crudely
                summary = entry.get("summary", entry.get("description", ""))
                summary = summary.replace("<p>", "").replace("</p>", " ")
                summary = summary.replace("<b>", "").replace("</b>", "")
                # Truncate
                summary = html_lib.unescape(summary)
                if len(summary) > 220:
                    summary = summary[:217].rsplit(" ", 1)[0] + "…"

                published = entry.get("published", "")
                link = entry.get("link", "#")

                entries.append({
                    "title":   html_lib.unescape(title),
                    "summary": summary,
                    "link":    link,
                    "source":  feed.feed.get("title", url),
                    "date":    published,
                })
        except Exception as e:
            print(f"  [warn] Could not fetch {url}: {e}")
        time.sleep(0.3)

    # Return first n (feeds are already sorted by recency)
    return entries[:n]


# ── EMAIL BUILDER ─────────────────────────────────────────────────────────────
def build_story_card(story, color):
    return f"""
    <div style="margin-bottom:16px; border-left:3px solid {color['accent']};
                padding:12px 16px; background:{color['bg']};
                border-radius:0 8px 8px 0;">
        <a href="{story['link']}" style="font-size:15px; font-weight:500;
                 color:{color['label']}; text-decoration:none; line-height:1.4;
                 display:block; margin-bottom:6px;">
            {story['title']}
        </a>
        <p style="margin:0 0 6px; font-size:13px; color:#444; line-height:1.5;">
            {story['summary']}
        </p>
        <span style="font-size:11px; color:#888;">{story['source']}</span>
    </div>"""


def build_section(category, stories):
    color = CATEGORY_COLORS[category]
    icon  = CATEGORY_ICONS[category]
    cards = "".join(build_story_card(s, color) for s in stories)
    return f"""
    <div style="margin-bottom:28px;">
        <h2 style="margin:0 0 12px; font-size:13px; font-weight:600;
                   text-transform:uppercase; letter-spacing:0.07em;
                   color:{color['accent']};">
            {icon}&nbsp; {category}
        </h2>
        {cards}
    </div>"""


def build_email(all_sections):
    today = datetime.now().strftime("%A, %B %-d, %Y")
    total = sum(len(s) for s in all_sections.values())
    body = "".join(build_section(cat, stories)
                   for cat, stories in all_sections.items() if stories)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0; padding:0; background:#f5f5f3; font-family:-apple-system,
             BlinkMacSystemFont,'Segoe UI',sans-serif;">

  <div style="max-width:600px; margin:24px auto; background:#fff;
              border-radius:12px; overflow:hidden;
              border:1px solid #e0e0dc;">

    <!-- Header -->
    <div style="background:#1a1a1a; padding:24px 28px;">
      <p style="margin:0; font-size:11px; color:#888; letter-spacing:0.08em;
                text-transform:uppercase;">Morning Digest</p>
      <h1 style="margin:4px 0 0; font-size:22px; font-weight:500; color:#fff;">
        {today}
      </h1>
      <p style="margin:6px 0 0; font-size:13px; color:#aaa;">
        {total} stories across economics, environmental policy &amp; college admissions
      </p>
    </div>

    <!-- Body -->
    <div style="padding:24px 28px;">
      {body}
    </div>

    <!-- Footer -->
    <div style="padding:16px 28px; border-top:1px solid #eee; background:#fafafa;">
      <p style="margin:0; font-size:11px; color:#bbb; text-align:center;">
        Delivered automatically via GitHub Actions · Economics Digest
      </p>
    </div>

  </div>
</body>
</html>"""


# ── EMAIL SENDER ──────────────────────────────────────────────────────────────
def send_email(html_body):
    today = datetime.now().strftime("%b %-d")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📰 Morning Digest — {today}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENT_EMAIL, msg.as_string())
    print(f"✅ Digest sent to {RECIPIENT_EMAIL}")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"🔍 Fetching stories — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    all_sections = {}
    for category, urls in FEEDS.items():
        n = STORIES_PER_CATEGORY[category]
        print(f"  [{category}] fetching {n} stories…")
        stories = fetch_top_stories(urls, n)
        all_sections[category] = stories
        print(f"  [{category}] got {len(stories)} stories")

    html_body = build_email(all_sections)
    send_email(html_body)


if __name__ == "__main__":
    main()
