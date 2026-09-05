"""
Fort Portal / Western Uganda Daily Job Alert Bot
--------------------------------------------------
Checks Ugandan job boards for new postings mentioning Fort Portal or
Western Uganda districts, and emails any NEW ones (not seen before) to
your subscriber list automatically.

Designed to run once a day via a free scheduler (GitHub Actions cron).
No server, no manual running, no cost.

Setup instructions are in README.md.
"""

import os
import json
import re
import smtplib
import imaplib
import email as email_lib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")          # e.g. your Gmail address
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")  # Gmail App Password
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
IMAP_SERVER = "imap.gmail.com"

SEEN_JOBS_FILE = "seen_jobs.json"
SUBSCRIBERS_FILE = "subscribers.txt"

# Keywords that mean a job is relevant to Fort Portal / Western Uganda.
# Add more district/town names here any time.
LOCATION_KEYWORDS = [
    "fort portal", "kabarole", "bunyangabu", "kasese", "kyenjojo",
    "kamwenge", "ntoroko", "bundibugyo", "kyegegwa", "western uganda",
    "rwenzori", "hoima", "kagadi", "kibaale",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}

# Each source: a name, the listing page to check, and how to pull job
# links + titles out of that page. Sites change their HTML sometimes,
# so this is the part most likely to need small fixes over time.
SOURCES = [
    {
        "name": "JobAdverts.ug",
        "url": "https://jobadverts.ug/?s=fort+portal",
        "link_selector": "a.job-title, h2 a, h3 a",
    },
    {
        "name": "TheUgandanJobline",
        "url": "https://theugandanjobline.com/search/label/fort-portal",
        "link_selector": "h3.post-title a, h2.post-title a",
    },
    {
        "name": "GreatUgandaJobs",
        "url": "https://www.greatugandajobs.com/search/?q=fort+portal",
        "link_selector": "a.job-title, h2 a, h3 a",
    },
]


# ---------------------------------------------------------------------------
# STATE (which jobs we've already posted, so we never repeat one)
# ---------------------------------------------------------------------------

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen), f, indent=2)


# ---------------------------------------------------------------------------
# SCRAPING
# ---------------------------------------------------------------------------

def is_relevant(text):
    text = text.lower()
    return any(keyword in text for keyword in LOCATION_KEYWORDS)


def fetch_jobs_from_source(source):
    """Returns a list of (title, url) tuples found on this source's page."""
    jobs = []
    try:
        resp = requests.get(source["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[{source['name']}] Could not fetch page: {e}")
        return jobs

    soup = BeautifulSoup(resp.text, "html.parser")
    links = soup.select(source["link_selector"])

    for link in links:
        title = link.get_text(strip=True)
        href = link.get("href")
        if not title or not href:
            continue
        if not href.startswith("http"):
            continue
        # Only keep jobs whose title mentions a relevant location.
        # (Some sources are already Fort-Portal-filtered by URL, so we
        # still keep those even if the title itself doesn't repeat it.)
        jobs.append((title, href))

    return jobs


def collect_new_jobs():
    seen = load_seen_jobs()
    new_jobs = []

    for source in SOURCES:
        print(f"Checking {source['name']}...")
        found = fetch_jobs_from_source(source)
        for title, url in found:
            if url in seen:
                continue
            # Keep if the URL/page was already location-filtered by the
            # source, OR the title itself mentions a relevant place.
            if is_relevant(title) or is_relevant(url):
                new_jobs.append({"title": title, "url": url, "source": source["name"]})
                seen.add(url)
        time.sleep(1)  # be polite between requests

    save_seen_jobs(seen)
    return new_jobs


# ---------------------------------------------------------------------------
# SUBSCRIBERS
# ---------------------------------------------------------------------------

def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []
    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        f.write("# Add one email address per line below.\n")
        f.write("# Lines starting with # are ignored.\n")
        for sub in sorted(set(subscribers)):
            f.write(sub + "\n")


def extract_email_address(from_header):
    """Pulls a bare email address out of a header like 'Name <a@b.com>'."""
    match = re.search(r"[\w\.\+\-]+@[\w\-]+\.[\w\.\-]+", from_header)
    return match.group(0).lower() if match else None


def send_plain_email(subject, body_text, recipient):
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print(f"Email not configured - would send to {recipient}:\n{body_text}")
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = recipient
    msg.attach(MIMEText(body_text, "plain"))
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, recipient, msg.as_string())


def process_subscription_requests():
    """
    Checks the inbox for unread emails with 'subscribe' or 'unsubscribe'
    in the subject line, updates subscribers.txt accordingly, and sends
    a short confirmation reply. People join or leave just by emailing you
    directly - no manual work on your end.
    """
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("Email not configured - skipping subscription check.")
        return

    subscribers = set(load_subscribers())
    changed = False

    try:
        imap = imaplib.IMAP4_SSL(IMAP_SERVER)
        imap.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        imap.select("INBOX")

        for keyword, action in (("subscribe", "add"), ("unsubscribe", "remove")):
            status, data = imap.search(None, f'(UNSEEN SUBJECT "{keyword}")')
            if status != "OK":
                continue
            for msg_id in data[0].split():
                status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                msg = email_lib.message_from_bytes(msg_data[0][1])
                sender = extract_email_address(msg.get("From", ""))
                if not sender:
                    continue

                # "unsubscribe" also contains "subscribe" as a substring,
                # so re-check the real subject to route correctly.
                subject_line = (msg.get("Subject") or "").lower()
                real_action = "remove" if "unsubscribe" in subject_line else "add"

                if real_action == "add" and sender not in subscribers:
                    subscribers.add(sender)
                    changed = True
                    send_plain_email(
                        "You're subscribed to Fort Portal Job Alerts",
                        "You're now subscribed! You'll get an email whenever "
                        "a new Fort Portal / Western Uganda job is posted.\n\n"
                        "To stop anytime, just email this address again with "
                        "the subject 'Unsubscribe'.",
                        sender,
                    )
                    print(f"Added subscriber: {sender}")
                elif real_action == "remove" and sender in subscribers:
                    subscribers.discard(sender)
                    changed = True
                    send_plain_email(
                        "You're unsubscribed from Fort Portal Job Alerts",
                        "You've been removed from the list and won't receive "
                        "any more alerts. Email 'Subscribe' anytime to rejoin.",
                        sender,
                    )
                    print(f"Removed subscriber: {sender}")

                imap.store(msg_id, "+FLAGS", "\\Seen")

        imap.logout()
    except Exception as e:
        print(f"Could not check for subscription requests: {e}")
        return

    if changed:
        save_subscribers(subscribers)


# ---------------------------------------------------------------------------
# EMAIL SENDING
# ---------------------------------------------------------------------------

def build_email_html(jobs):
    rows = ""
    for job in jobs:
        rows += (
            f"<li style='margin-bottom:14px;'>"
            f"<a href='{job['url']}' style='font-size:16px;font-weight:bold;"
            f"color:#1F3864;text-decoration:none;'>{job['title']}</a><br>"
            f"<span style='color:#555;font-size:13px;'>"
            f"📍 Fort Portal / Western Uganda &nbsp;|&nbsp; via {job['source']}"
            f"</span></li>"
        )
    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;">
      <h2 style="color:#1F3864;">Fort Portal Job Alerts — {len(jobs)} new job(s) today</h2>
      <ul style="list-style:none;padding-left:0;">
        {rows}
      </ul>
      <p style="color:#888;font-size:12px;">
        You're receiving this because you subscribed to Fort Portal Job Alerts.
      </p>
    </body>
    </html>
    """


def send_email(subject, html_body, recipients):
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        print("Email not configured - printing instead:\n")
        print(html_body)
        return

    if not recipients:
        print("No subscribers in subscribers.txt - nothing to send.")
        return

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)

        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = EMAIL_ADDRESS
            msg["To"] = recipient
            msg.attach(MIMEText(html_body, "html"))
            try:
                server.sendmail(EMAIL_ADDRESS, recipient, msg.as_string())
                print(f"Sent to {recipient}")
            except smtplib.SMTPException as e:
                print(f"Failed to send to {recipient}: {e}")
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    process_subscription_requests()

    new_jobs = collect_new_jobs()

    if not new_jobs:
        print("No new Fort Portal / Western Uganda jobs found today.")
        return

    recipients = load_subscribers()
    subject = f"🆕 {len(new_jobs)} new Fort Portal job(s) today"
    html_body = build_email_html(new_jobs)

    print(f"Found {len(new_jobs)} new job(s). Emailing {len(recipients)} subscriber(s)...")
    send_email(subject, html_body, recipients)

    print("Done.")


if __name__ == "__main__":
    main()
