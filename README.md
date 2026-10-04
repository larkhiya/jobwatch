# jobwatch

A small bot that checks [OnlineJobs.ph](https://www.onlinejobs.ph/jobseekers/jobsearch) every 15 minutes
for newly posted developer jobs and sends each new match to your phone through [ntfy](https://ntfy.sh)
(a free push-notification app that needs no account), or optionally Telegram.
It runs on GitHub Actions, so your computer doesn't need to be on, and everything it uses is free.

Optional extras, each set up separately:

- **A web app you can install on your iPhone.** It's an inbox of every matching job where you mark
  Save / Applied / Skip and keep notes. See [The web app and iPhone](#the-web-app-and-iphone-optional).
- **AI with Claude, on your own Claude plan.** You get a fit score in each alert, and an **Analyze**
  button that lists your strengths, your gaps, how to become a stronger candidate, and a draft
  application. See [AI features](#ai-features-optional).

## How it works

Every run is short and does the same steps, then exits:

```
fetch the newest-jobs page → parse 30 job cards → drop IDs already seen → keyword filter
→ notify → save state/seen.json → the workflow commits state/ back to the repo
```

- **No server.** GitHub starts a fresh machine every 15 minutes, runs `python -m jobwatch`, and throws the
  machine away. The only memory between runs is `state/`, which the workflow commits to the repo.
- **Dedupe by job ID.** Each job URL ends in a number (`.../senior-wordpress-developer-1742846`), and that
  number is the ID. IDs are kept for 45 days.
- **First run = seed.** The first run records everything currently listed *without* notifying, so you don't
  get flooded with old jobs. You get one "jobwatch is running" message instead.
- **Health checks**, so silence never means "maybe it's dead":
  - a daily heartbeat
  - a "parser may be broken" alert if the page loads but no jobs are found
  - a "run failed" alert on errors

  Alerts are rate-limited.
- **Polite client**:
  - one page request per run, never more often than every 15 minutes
  - a 20-second timeout
  - at most 3 retries, and only for temporary errors
  - a descriptive User-Agent

  If the site blocks requests, jobwatch reports it and stops trying. It never tries to get around a block.

> **Terms of use:** OnlineJobs.ph's Terms (§7.4) prohibit automated access unless they've given express
> permission. robots.txt doesn't disallow the search page. Running this bot is your own decision. If you
> want to be fully in the clear, ask OnlineJobs for permission through their contact page.

---

## Setup (about 10 minutes)

### 1. Pick a secret topic name

ntfy works with **topics**. Anyone who sends to a topic name reaches everyone subscribed to it, and there's no
login. That means **the topic name works like a password**: make it long and random so nobody can guess it.

Generate one in PowerShell:

```powershell
"jobwatch-" + -join ((48..57) + (97..122) | Get-Random -Count 16 | ForEach-Object {[char]$_})
```

You'll get something like `jobwatch-k3x9q2m7v8w1z5r4`. Use only letters, digits, `-` and `_`, up to 64
characters. Keep it private: don't commit it, post it, or share screenshots of it.

### 2. Install ntfy on your phone and subscribe

1. Install **ntfy** from Google Play / F-Droid (Android) or the App Store (iPhone). It's free.
2. Open it, tap **+** (Subscribe to topic), and type your topic name *exactly*.
   Leave the server as the default `ntfy.sh`. No account or sign-up is needed.
3. Optional test: open `https://ntfy.sh/<your-topic>` in a browser on your computer, type a message, and
   press send. It should pop up on your phone within a few seconds.

On Android, if notifications arrive late, open the ntfy app settings and allow it to ignore battery
optimization.

### 3. Put the code on GitHub (public repository)

The repository must be **public**. Actions minutes are free and unlimited for public repos. A private repo
would need about 2,880 minutes a month on this schedule, which is more than the 2,000 free minutes.

Create an empty public repo named `jobwatch` on GitHub, then from this folder:

```bash
git remote add origin https://github.com/<your-username>/jobwatch.git
```

```bash
git push -u origin main
```

### 4. Add your secret

On GitHub, open your repo, then go to **Settings → Secrets and variables → Actions → New repository secret**.

| Name         | Secret value                                                                   |
| ------------ | ------------------------------------------------------------------------------ |
| `NTFY_TOPIC` | your topic name from step 1, just the name (not `https://ntfy.sh/...`)         |

The name `NTFY_TOPIC` must match exactly. Secrets are encrypted, GitHub hides them in logs, and jobwatch
only reads them from environment variables.

### 5. First runs

1. Open the **Actions** tab. If GitHub asks, click **"I understand my workflows, go ahead and enable them"**.
2. Click **jobwatch** in the left sidebar, then **Run workflow**, tick **dry_run**, and click **Run workflow**.
3. Open the run and check the log of the **Check for new jobs** step. You should see `Listings found: 30`.
   That confirms GitHub's servers can reach the site. If you see `BlockedError`, read
   [Blocked](#run-failed--site-appears-to-be-blocking) below.
4. Click **Run workflow** again, this time *without* dry_run. Your phone should get the notification
   **"jobwatch is running"**, and a commit "Update job state [skip ci]" appears in the repo.
5. That's it. The schedule takes over from here (every 15 minutes, though GitHub may run it a bit late).

---

## The web app and iPhone (optional)

A private inbox for every matching job: tabs for New / Saved / Applied / Skipped, search, notes, and links to
each post. Behind it is a free [Supabase](https://supabase.com) database; the bot fills it every run.
On iPhone it installs from Safari like a normal app. There's no App Store and no cost.

```
GitHub Actions bot ──writes jobs──▶ Supabase (private database) ◀──reads/writes── web app (GitHub Pages)
```

Before setup, the site shows **demo data**, so you can try it first.

### A. Create the database (about 10 minutes)

1. Go to [supabase.com](https://supabase.com), click **Start your project**, and **sign in with GitHub**.
2. Click **New project**:
   - **Name:** `jobwatch`
   - **Database password:** let it generate one and save it in your password manager. jobwatch never
     needs it.
   - **Region:** Southeast Asia (Singapore)
   - **Plan:** Free

   Then click **Create**.
3. Open **SQL Editor** → **New query**, paste the whole of [`supabase/schema.sql`](supabase/schema.sql),
   and click **Run**. You should see "Success. No rows returned".
4. Open **Project Settings → API Keys** and note three things:
   - your **Project URL**, like `https://abcdefghijkl.supabase.co`
   - the **publishable key** (`sb_publishable_...`)
   - a **secret key** (`sb_secret_...`). If there isn't one, create it on that page.

   The secret key can read and change everything, so never paste it anywhere except the GitHub secret
   below.
5. Open **Authentication → URL Configuration**. Set **Site URL** to
   `https://<your-username>.github.io/jobwatch/`, and add the same address under **Redirect URLs**.
6. Open **Authentication → Emails → Magic Link** (the sign-in email template). Add this line to the
   message body and save:

   ```
   Your code: {{ .Token }}
   ```

   That puts a 6-digit code in the sign-in email. The iPhone app needs it (see C below).

### B. Connect GitHub (about 5 minutes)

In your repo, go to **Settings → Secrets and variables → Actions**:

| Tab           | Name                       | Value                                   |
| ------------- | -------------------------- | --------------------------------------- |
| **Secrets**   | `SUPABASE_SECRET_KEY`      | the `sb_secret_...` key                 |
| **Variables** | `SUPABASE_URL`             | your Project URL                        |
| **Variables** | `SUPABASE_PUBLISHABLE_KEY` | the `sb_publishable_...` key            |

The URL and publishable key are *variables*, not secrets, because they're meant to be public: the web
page needs them. Your data is protected by sign-in and the database's access rules, not by hiding
these two values.

Then go to **Settings → Pages**, set **Source** to **GitHub Actions**, open **Actions → web → Run
workflow**, and wait about a minute. The app is now at `https://<your-username>.github.io/jobwatch/`.
From the next bot run on, new listings appear in it.

### C. Sign in, and lock it to you

1. Open the app, enter your email, then type the code from the email. On a laptop, tapping the link in
   the email works too.
2. The first time, you'll see **Almost there** with a short SQL snippet. Run it in the Supabase **SQL
   Editor** and reload. That adds you to the allow-list. Only allow-listed accounts can see any data, so
   even if a stranger signed up they'd see nothing.
3. Close sign-ups: **Authentication → Sign In / Providers → Email**, turn off **Allow new users to sign
   up**, and save.

### D. Install on your iPhone

1. Open `https://<your-username>.github.io/jobwatch/` in **Safari**. It has to be Safari: other browsers
   on iPhone can't add web apps to the Home Screen.
2. Tap **Share** (the square with an arrow), then **Add to Home Screen**, then **Add**.
3. Open **jobwatch** from your Home Screen and sign in with an emailed **code**. An app on the Home
   Screen keeps its own login, separate from Safari, so a sign-in link would log in Safari instead of the
   app. It stays signed in after that.

It needs an internet connection, as the jobs live in the database. Your alerts still come through ntfy.

---

## AI features (optional)

Claude reads each new match and your profile, and gives a **fit score (0–100) with a one-line reason** in
the alert and the app. Tap **Analyze with AI** on any job for a deeper look: strengths, gaps, red flags,
**how to become a stronger candidate**, and a **draft application** to edit and send yourself. It never
applies for you.

**What it costs:** it runs on your Claude plan through the
[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview), so there's no separate bill. It
uses the same usage limits as your normal Claude chats and Claude Code, so the bot keeps it small:
- **Batching:** each run scores all its new matches in one request.
- **Daily caps:** see `ai:` in `config.yaml`.
- **Usage report:** the daily heartbeat says how many tokens it used.

If you hit a limit, alerts simply go out without scores until it resets.

**Set it up** (needs the web app above):

1. **Write your profile.** In the app, tap **Profile** and describe your skills, years of experience, real
   projects, your portfolio link, the hours and pay you want, and what you don't want. Claude compares
   every job against this, so specific beats short. Don't put passwords or ID numbers in it.
2. **Get a token for your Claude plan.** On your computer, install
   [Claude Code](https://code.claude.com/docs/en/setup) if you haven't, then run:

   ```bash
   claude setup-token
   ```

   It opens a browser to sign in, then prints a long token. The token lasts one year, and is a key to your
   Claude plan, so treat it like a password.
3. In GitHub **Settings → Secrets and variables → Actions**:
   - **Secrets:** add `CLAUDE_CODE_OAUTH_TOKEN` with that token.
   - **Variables:** add `AI_ENABLED` with the value `true`.
4. Re-run **Actions → web** so the app shows the AI buttons, then run **Actions → jobwatch** once. Its log
   should contain lines like `AI: scored 2 of 2 jobs (3,100 in / 400 out tokens)`.

**Tuning** (the `ai:` section of `config.yaml`):
- **`max_scores_per_day` / `max_analyses_per_day`:** your daily caps.
- **`min_score_to_alert`:** for example `50` means only jobs Claude scores 50+ ping your phone. The rest
  still show in the app.
- **`model`:** which Claude model it uses.
- **`web.app_url`:** set it to your app's address so "Analysis ready" alerts open the app.

**To turn it off:** set the `AI_ENABLED` variable to `false`, then re-run **Actions → web**.

---

## Day to day

### Messages you'll get

| Message                         | Meaning                                                                       |
| ------------------------------- | ----------------------------------------------------------------------------- |
| a job title + link              | a new matching job (title, type, salary, posted time in PHT, link)            |
| "N new developer jobs…"         | more than 5 matches in one run, sent as one digest instead of a flood         |
| "jobwatch heartbeat"            | once a day, on the first run after 08:00 PHT: listings checked, jobs sent, runs, errors |
| "jobwatch: parser may be broken"| the page loaded but no jobs were found (at most once per 24h)                 |
| "jobwatch: run failed"          | an error happened (at most once per 6h); the Actions run is also marked red   |
| "Fit 82/100 · apply: …" line    | (AI on) Claude's fit score and reason, at the top of a job alert               |
| "Analysis ready: …"             | (AI on) the analysis you asked for is in the app                               |

### Changing keywords

Edit `config.yaml`. You can do it right on GitHub: open the file, click the pencil icon, then **Commit changes**.
The next run uses the new keywords.

```yaml
filters:
  include_keywords: [developer, programmer, react, ...]  # a job must match at least one
  exclude_keywords: [commission only, unpaid]            # any match rejects the job
```

How matching works:
- It looks at the job title, the description snippet, and the category tags.
- Case doesn't matter, and it matches whole words: `react` doesn't match "reactive", and `developer`
  doesn't match "development".
- Spaces and hyphens are interchangeable: `full stack` matches "Full-Stack" and "fullstack".
- A plural "s" is fine: `developer` matches "Developers".

**Tip:** run a dry run (locally or from the Actions tab). It prints a *filter preview* of which jobs on the
current page match your keywords, so you can tune them without waiting for new posts.

Other settings in `config.yaml`:
- the digest threshold
- the heartbeat hour and time zone
- the alert cooldowns
- how long IDs are remembered
- `source.pages`: how many result pages to check

### Reading the logs

Go to **Actions → jobwatch → (a run) → check → "Check for new jobs"**. Each run ends with a line like:

```
Listings found: 30 | new: 4 | matched: 1 | notified: 1
```

Lines starting with `Match (react): …` show which keyword triggered each alert.

---

## Running it on your computer

You'll need [uv](https://docs.astral.sh/uv/) (or any Python 3.12). From the project folder:

```bash
uv venv --python 3.12 .venv
```

```bash
uv pip install --python .venv -r requirements.txt
```

```bash
.venv/Scripts/python -m pytest
```

```bash
.venv/Scripts/python -m jobwatch --dry-run
```

On macOS or Linux, use `.venv/bin/python` instead of `.venv/Scripts/python`.

- `pytest` runs all the tests offline against saved copies of the page in `tests/fixtures/`.
- `--dry-run` fetches the live page and prints what *would* be sent. It needs no secrets and saves nothing.
- `--seed` records the current listings as seen without sending job alerts.

**Locally, stick to `--dry-run`.** A real local run changes `state/`, which the bot on GitHub also commits
every 15 minutes, so the two would conflict. Always `git pull` before editing files locally.

To send a real test message from your computer (PowerShell):

```powershell
$env:NTFY_TOPIC = "your-topic-name"
```

Then run `.venv/Scripts/python -m jobwatch` once. If there's no `state/` yet, it seeds and sends
"jobwatch is running", which is a good end-to-end test. Afterwards, throw away the local state:
delete `state/` if it didn't exist before, otherwise run `git checkout -- state`.

### Using Telegram instead of ntfy (optional)

You need to be able to sign in to Telegram for this.

1. In Telegram, open a chat with **@BotFather**, send `/newbot`, and pick a name and a username ending in
   `bot`. BotFather replies with a **token** (`123456789:AAH...`). Treat it as a password.
2. Open a chat with your new bot and press **Start**. Then open
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and find `"chat":{"id":123456789`.
   That number is your **chat ID**.
3. Add GitHub secrets `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
4. In `config.yaml`, set `notify: channel: telegram`.

---

## Troubleshooting

### No alerts at all

1. **Did you get a heartbeat this morning?** If yes, the bot is fine and there were simply no new matching
   jobs. Run a dry run and look at the filter preview to check your keywords.
2. **Are runs happening?** Look at the Actions tab. If there are no recent runs, see
   [Workflow disabled](#workflow-disabled) below.
3. **Are runs red?** Open one and look at the error:
   - `Missing environment variable(s)`: the `NTFY_TOPIC` secret is missing or misnamed (see step 4).
   - `NTFY_TOPIC must be just the topic name`: you pasted the full URL. Paste only the part after
     `ntfy.sh/`.
   - `ntfy HTTP 429`: ntfy.sh's free rate limit was hit, which is rare at this volume. The jobs are retried
     on the next run.
4. **Runs are green and say `notified: 1`, but your phone shows nothing?** The topic in the app doesn't
   exactly match the secret (it's case-sensitive). Re-subscribe with the exact name. On Android, also allow
   ntfy to ignore battery optimization.

With Telegram: `Telegram HTTP 400: chat not found` means the chat ID is wrong or you never pressed
**Start** in your bot's chat. `Telegram HTTP 401` means the token is wrong.

### "Parser may be broken"

The page loaded, but no job cards were found. OnlineJobs.ph probably changed its HTML. To fix it:

1. Open the [job search page](https://www.onlinejobs.ph/jobseekers/jobsearch) in your browser and save
   it (**Ctrl+S**, "Webpage, HTML only") as `tests/fixtures/jobsearch_latest.html`.
2. Run `.venv/Scripts/python -m pytest tests/test_parse.py` and see what fails.
3. Update the CSS selectors in `jobwatch/parse.py` (`div.jobpost-cat-box`, `h4`, `p[data-temp-2]`, …) to
   match the new HTML. Then update the expected values in `tests/test_parse.py`.
4. Commit and push. The tests workflow checks your fix, and the next scheduled run uses it.

### "Run failed … site appears to be blocking"

OnlineJobs.ph answered with HTTP 403/429 or a "verify you are human" page, and is blocking automated
requests, probably from GitHub's data-center IP addresses. **jobwatch deliberately doesn't work around
this**: no proxies, no CAPTCHA solving, no faster retries. What to do:

1. Disable the workflow (**Actions → jobwatch → ⋯ → Disable workflow**) so it stops trying.
2. Free, legitimate alternatives:
   - **Run it from home on an always-on device.** For example, an old Android phone with
     [Termux](https://termux.dev) (install Python, clone the repo, schedule it with `crontab`), or a
     Raspberry Pi. Same code, same commands. It's your normal home connection making one request
     every 15 minutes.
   - **Ask OnlineJobs.ph for permission** or an official feed (their Terms §7.4 allow automated access
     with permission).

### Workflow disabled

GitHub automatically disables scheduled workflows in a public repo after **60 days without repository
activity**. The bot's state commits normally count as activity, but if it happens, open
**Actions → jobwatch** and click **Enable workflow**.

Also check **Settings → Actions → General**: Actions must be allowed for the repo.

### Runs are late or missing

GitHub's schedule is best-effort. At busy times, runs can start 5–30 minutes late or occasionally be skipped.
The heartbeat's "runs" count shows how many actually ran. The maximum is 96 per day.

The workflow runs at minutes 7, 22, 37 and 52 instead of on the hour, because GitHub says the start of each
hour is its busiest time for scheduled runs.

If there are **no** scheduled runs at all for over an hour after you set up or re-enable the workflow,
GitHub may not have registered the schedule. Push any small change to `.github/workflows/jobwatch.yml`, or
switch the workflow off and on again (**Actions → jobwatch → ⋯ → Disable**, then **Enable**).

A missed run doesn't lose jobs as long as fewer than 30 jobs were posted in between. If the log says
`Possible gap`, consider setting `source.pages: 2` in `config.yaml`.

### Lots of "Run failed" emails from GitHub

GitHub emails you about failed runs. If something is broken for a while, disable the workflow until it's
fixed (see above). jobwatch's own error alerts are already limited to one every 6 hours.

### Web app: empty inbox, or no sign-in email

- **"Almost there" screen:** you're signed in but not on the allow-list yet. Run the SQL it shows in the
  Supabase SQL Editor.
- **Inbox is empty:** check the Actions log for `Saved 30 listings to the database`. A warning
  `Database not updated: … is missing` names the setting you still need from step B.
- **No email:** check spam. Supabase's free built-in email only sends a few sign-in emails per hour,
  so wait a bit before trying again.
- **The email has a link but no code:** step A6, the `{{ .Token }}` line, is missing.
- **The app still says "Demo data":** the variables from step B aren't set, or **Actions → web** hasn't
  run since you set them.

### AI: no scores

Look in the **jobwatch** run log for lines starting with `AI`:
- **`no profile yet`:** save your profile in the app.
- **`AI is switched on but not running`:** the message names the missing piece.
- **`daily scoring limit reached`:** the daily cap in `config.yaml` was hit.
- **`AI scoring skipped: …`:** Claude was unavailable. This could be your plan's usage limit, or an
  expired token (it lasts a year; run `claude setup-token` again and update the secret).

Alerts keep working without scores in every one of these cases.

### Got the same job twice

Rare, and by design. A job is only marked seen *after* its message is delivered, so if a run dies right after
sending (before saving), the job is sent again next time. That's better than silently missing it.

---

## Project layout

```
jobwatch/
  __main__.py   CLI: python -m jobwatch [--dry-run] [--seed] [--config PATH]
  app.py        one run: fetch → parse → dedupe → filter → notify → save; error/heartbeat handling
  config.py     loads config.yaml + secrets from env vars, validates them
  fetch.py      HTTP: timeout, retries with backoff, User-Agent, block detection
  parse.py      HTML → Job(id, title, url, posted, salary, snippet, job_type, tags)
  store.py      state/seen.json: load, atomic save, prune
  filters.py    include/exclude keyword matching
  notify.py     message formatting + Telegram / ntfy / print senders
  health.py     state/health.json: alert cooldowns, heartbeat counters, AI usage
  db.py         (optional) saves listings and AI results to Supabase
  ai.py         (optional) Claude fit scores and analyses via the Agent SDK
config.yaml     settings (no secrets)
state/          created by the first run, then committed by the workflow
supabase/schema.sql   database tables + access rules, run once in Supabase
web/            the React web app (installable on iPhone); see web/README.md
tests/          offline tests; fixtures/ holds saved copies of the site's pages
.github/workflows/jobwatch.yml   the 15-minute schedule
.github/workflows/web.yml        builds the web app and publishes it to GitHub Pages
.github/workflows/tests.yml      runs the Python and web tests on every push
```
