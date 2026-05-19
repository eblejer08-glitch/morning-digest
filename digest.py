import feedparser
import urllib.request
import urllib.parse
import urllib.error
import json
import io
import os
import time
import html as html_lib
from datetime import datetime

feedparser.USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 NewsDigest/1.0"
)

RESEND_API_KEY  = os.environ["RESEND_API_KEY"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]
SENDER_EMAIL    = "onboarding@resend.dev"

FEEDS = {
    "Economics": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.imf.org/en/News/rss?language=eng",
        "https://feeds.feedburner.com/wsj/xml/rss/3_7031.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
        "https://feeds.bloomberg.com/economics/news.rss",
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
    ],
}

STORIES_PER_CATEGORY = {
    "Economics":            2,
    "Environmental Policy": 2,
    "College Admissions":   1,
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


def fetch_feed(url):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": feedparser.USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        return feedparser.parse(io.BytesIO(data))
    except Exception:
        return feedparser.parse(url)


def fetch_top_stories(feed_urls, n):
    entries = []
    seen = set()
    for url in feed_urls:
        try:
            feed = fetch_feed(url)
            for entry in feed.entries[:10]:
                title = entry.get("title", "").strip()
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                summary = entry.get("summary", entry.get("description", ""))
                for tag in ["<p>", "</p>", "<b>", "</b>", "<br>", "<br/>"]:
                    summary = summary.replace(tag, " ")
                summary = html_lib.unescape(summary).strip()
                if len(summary) > 220:
                    summary = summary[:217].rsplit(" ", 1)[0] + "…"
                entries.append({
                    "title":   html_lib.unescape(title),
                    "summary": summary,
                    "link":    entry.get("link", "#"),
                    "source":  feed.feed.get("title", url),
                })
        except Exception as e:
            print(f"  [warn] {url}: {e}")
        time.sleep(0.3)
    return entries[:n]


def build_story_card(story, color):
    return f"""
    <div style="margin-bottom:14px;border-left:3px solid {color['accent']};
                padding:12px 16px;background:{color['bg']};
                border-radius:0 8px 8px 0;">
      <a href="{story['link']}"
         style="font-size:15px;font-weight:500;color:{color['label']};
                text-decoration:none;line-height:1.4;display:block;margin-bottom:6px;">
        {story['title']}
      </a>
      <p style="margin:0 0 6px;font-size:13px;color:#444;line-height:1.5;">
        {story['summary']}
      </p>
      <span style="font-size:11px;color:#888;">{story['source']}</span>
    </div>"""


def build_section(category, stories):
    color = CATEGORY_COLORS[category]
    icon  = CATEGORY_ICONS[category]
    cards = "".join(build_story_card(s, color) for s in stories)
    return f"""
    <div style="margin-bottom:28px;">
      <h2 style="margin:0 0 12px;font-size:12px;font-weight:600;
                 text-transform:uppercase;letter-spacing:0.07em;
                 color:{color['accent']};">
        {icon}&nbsp; {category}
      </h2>
      {cards}
    </div>"""


def build_email(sections):
    today = datetime.now().strftime("%A, %B %-d, %Y")
    total = sum(len(s) for s in sections.values())
    body  = "".join(build_section(cat, stories)
                    for cat, stories in sections.items() if stories)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#f5f5f3;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:600px;margin:24px auto;background:#fff;
              border-radius:12px;overflow:hidden;border:1px solid #e0e0dc;">
    <div style="background:#1a1a1a;padding:24px 28px;">
      <p style="margin:0;font-size:11px;color:#888;letter-spacing:0.08em;
                text-transform:uppercase;">Morning Digest</p>
      <h1 style="margin:4px 0 0;font-size:22px;font-weight:500;color:#fff;">
        {today}
      </h1>
      <p style="margin:6px 0 0;font-size:13px;color:#aaa;">
        {total} stories · economics, environmental policy &amp; college admissions
      </p>
    </div>
    <div style="padding:24px 28px;">{body}</div>
    <div style="padding:16px 28px;border-top:1px solid #eee;background:#fafafa;">
      <p style="margin:0;font-size:11px;color:#bbb;text-align:center;">
        Delivered automatically via GitHub Actions
      </p>
    </div>
  </div>
</body>
</html>"""


def send_via_resend(html_body):
    today = datetime.now().strftime("%b %-d")
    payload = json.dumps({
        "from":    f"Morning Digest <{SENDER_EMAIL}>",
        "to":      [RECIPIENT_EMAIL],
        "subject": f"📰 Morning Digest — {today}",
        "html":    html_body,
    }).encode()

    print(f"Sending to: {RECIPIENT_EMAIL}")
    print(f"From: {SENDER_EMAIL}")
    print(f"API key starts with: {RESEND_API_KEY[:8]}...")

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
        print(f"✅ Sent! ID: {result.get('id')} → {RECIPIENT_EMAIL}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"❌ HTTP {e.code}: {e.reason}")
        print(f"❌ Response body: {error_body}")
        raise


def main():
    print(f"🔍 Fetching stories — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    sections = {}
    for category, urls in FEEDS.items():
        n = STORIES_PER_CATEGORY[category]
        print(f"  [{category}] fetching {n} stories…")
        stories = fetch_top_stories(urls, n)
        sections[category] = stories
        print(f"  [{category}] got {len(stories)}")

    html_body = build_email(sections)
    send_via_resend(html_body)


if __name__ == "__main__":
    main()
