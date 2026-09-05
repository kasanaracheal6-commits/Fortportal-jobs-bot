# Fort Portal Daily Job Alert Bot (Email Version)

Runs automatically, once a day, and emails any **new** Fort Portal /
Western Uganda job vacancies to everyone subscribed. People join or
leave the list themselves just by sending an email — you don't manage
the list by hand.

You do this setup **once**. After that, it's fully automatic.

---

## What you need (all free)

- A GitHub account (github.com)
- A Gmail account (this is the address people will email to join, and
  the address alerts get sent from)

---

## Step 1: Create a Gmail App Password

1. Go to https://myaccount.google.com/security and turn on
   **2-Step Verification** if it isn't on already.
2. Go to https://myaccount.google.com/apppasswords
3. Create a new app password (name it "Job Bot"). Copy the 16-character
   password shown (remove spaces) — this is your `EMAIL_APP_PASSWORD`.
4. Your Gmail address is your `EMAIL_ADDRESS`.

## Step 2: Put this code on GitHub

1. Create a free account at github.com if you don't have one.
2. Create a **New Repository** (e.g. `fortportal-jobs-bot`).
3. Upload every file in this folder to that repository (use "Add file" >
   "Upload files" on the GitHub website).

## Step 3: Add your secrets

1. In the repository: **Settings > Secrets and variables > Actions**.
2. Add two secrets:
   - `EMAIL_ADDRESS` — your Gmail address
   - `EMAIL_APP_PASSWORD` — the 16-character app password

## Step 4: Turn it on

1. Go to the **Actions** tab.
2. Click "Daily Fort Portal Job Alert" > **Run workflow** to test it now.
3. From then on, it runs itself **every morning at 8:00 AM EAT**.

---

## How people join or leave (fully self-service)

**To subscribe:** send an email to your Gmail address with the subject
line **"Subscribe"** (any body text, or empty). They'll get an automatic
confirmation reply and be added to the list.

**To unsubscribe:** send an email to the same address with the subject
line **"Unsubscribe"**. They're removed automatically.

You never have to touch the subscriber list by hand — share your Gmail
address on WhatsApp, Facebook, wherever, with instructions to email
"Subscribe", and the bot handles the rest each time it runs.

---

## Notes and honest limitations

- **New subscribers are only picked up once a day**, at the same time
  the job check runs — so someone who emails "Subscribe" gets confirmed
  and starts receiving alerts from the next day's run onward, not
  instantly.
- **Gmail's free sending limit is 500 emails/day** — plenty of room to
  grow before this becomes a real constraint.
- **Websites change their design sometimes.** If a source stops
  returning jobs, its HTML structure may have changed, and the
  `link_selector` in `job_bot.py` for that source will need a small
  update — normal for any scraper, not a sign it's broken beyond repair.
- **Starts with 3 sources** (JobAdverts.ug, TheUgandanJobline,
  GreatUgandaJobs). Add more by copying the pattern in the `SOURCES`
  list in `job_bot.py`.
- Only genuinely **new** jobs get emailed, tracked in `seen_jobs.json`,
  so nobody gets repeat alerts for the same posting.
