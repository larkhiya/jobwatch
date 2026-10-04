# jobwatch

A small bot that checks [OnlineJobs.ph](https://www.onlinejobs.ph/jobseekers/jobsearch) every 15 minutes
for newly posted developer jobs and sends each new match to your phone through [ntfy](https://ntfy.sh)
(a free push-notification app that needs no account), or optionally Telegram.
It runs on GitHub Actions, so your computer doesn't need to be on, and everything it uses is free.

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

## Day to day

### Messages you'll get

| Message                         | Meaning                                                                       |
| ------------------------------- | ----------------------------------------------------------------------------- |
| a job title + link              | a new matching job (title, type, salary, posted time in PHT, link)            |
| "N new developer jobs…"         | more than 5 matches in one run, sent as one digest instead of a flood         |
| "jobwatch heartbeat"            | once a day, on the first run after 08:00 PHT: listings checked, jobs sent, runs, errors |
| "jobwatch: parser may be broken"| the page loaded but no jobs were found (at most once per 24h)                 |
| "jobwatch: run failed"          | an error happened (at most once per 6h); the Actions run is also marked red   |

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

A missed run doesn't lose jobs as long as fewer than 30 jobs were posted in between. If the log says
`Possible gap`, consider setting `source.pages: 2` in `config.yaml`.

### Lots of "Run failed" emails from GitHub

GitHub emails you about failed runs. If something is broken for a while, disable the workflow until it's
fixed (see above). jobwatch's own error alerts are already limited to one every 6 hours.

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
  health.py     state/health.json: alert cooldowns, heartbeat counters
config.yaml     settings (no secrets)
state/          created by the first run, then committed by the workflow
tests/          offline tests; fixtures/ holds saved copies of the search page
.github/workflows/jobwatch.yml   the 15-minute schedule
.github/workflows/tests.yml      runs pytest on every push
```
