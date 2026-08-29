# Tele AI Agent — Phase 1, Step 1

This is the first, deliberately small part of Tele AI Agent. The eventual flow is:

```text
Telegram → AI → SQLite → Notion
```

This repository now implements the **full Phase 1 pipeline: Telegram → AI → SQLite →
Notion**. It authenticates a local Telegram account, retrieves messages from a single
chat or every chat inside a Telegram folder, and prints structured message data to the
terminal. An optional `--ai-filter` flag classifies each message with Claude Sonnet 5
(event/task/important/information/ignore), extracts structured details (dates, times,
locations, deadlines), and persists both the message and its classification to a local
SQLite database — so a message is never sent to the AI twice. An optional `--sync-notion`
flag then creates a Notion page for each not-yet-synced result. No menu-bar UI yet.

## Progress so far

- [x] Authenticate a local Telegram account (Telethon, interactive phone/code login)
- [x] Read messages from a single chat by username, numeric ID, or invite link
- [x] Read messages from every chat inside a named Telegram folder
- [x] Filter messages by minimum message ID and/or timestamp
- [x] Print structured message data to the terminal
- [x] AI classification/extraction layer via `--ai-filter` (Claude, Milestone 2)
- [x] Persist messages and AI results to SQLite; skip re-processing already-seen messages (Milestone 3)
- [x] Sync AI results to Notion via `--sync-notion`; skip already-synced results (Milestone 4)
- [x] Optional macOS desktop widget showing upcoming events/tasks from Notion (see [Desktop widget](#desktop-widget-optional-macos))

## Prerequisites

- Python 3.10 or newer (`python3 --version`)
- A Telegram account
- Telegram API credentials: sign in at [my.telegram.org/apps](https://my.telegram.org/apps),
  create an API application, and copy its API ID and API hash.

## Installation

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure the environment

Create your private configuration file:

```bash
cp .env.example .env
```

Then edit `.env` and fill in:

```dotenv
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_TEST_CHAT=some_chat_username
ANTHROPIC_API_KEY=your_anthropic_api_key
NOTION_API_KEY=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id
```

`TELEGRAM_TEST_CHAT` can be a username, a numeric ID, or an invite link that your
account can access. `ANTHROPIC_API_KEY` is only required if you use `--ai-filter`
(get one at [console.anthropic.com](https://console.anthropic.com); a Google Gemini
free-tier key was tried first but turned out to require prepaid billing credits even
on nominally-free models, so this app uses Claude instead). `NOTION_API_KEY` and
`NOTION_DATABASE_ID` are only required if you use `--sync-notion` — see
[Syncing to Notion](#syncing-to-notion-sync-notion) below for setup. `.env` and the
generated Telethon session file are ignored by Git.

## Run

With the virtual environment active:

```bash
python -m app.main
```

If you don't pass `--after-id` or `--after-timestamp`, the app automatically only
retrieves messages from the last 24 hours (printing the exact cutoff it used) — this
is what makes a plain daily invocation naturally cover "yesterday" without extra
flags. Pass either flag yourself to override this:

```bash
python -m app.main --chat some_chat_username --limit 10
python -m app.main --after-id 12345
python -m app.main --after-timestamp 2026-08-16T01:30:00+00:00
```

Read every chat inside a Telegram folder instead of a single chat with `--folder`
(this is mutually exclusive with `--chat`):

```bash
python -m app.main --folder "My Folder Name" --limit 5
```

If you omit both `--chat` and `--folder`, the app looks for a `## Folders to query`
section in `template.md` and processes every folder listed there in one run (see
below) — useful once you're monitoring more than one folder and don't want to remember
folder names on the command line each time. Falls back to `TELEGRAM_TEST_CHAT` if that
section is absent or empty.

Messages are printed oldest to newest after the optional filters are applied. The
message-ID filter is delegated to Telegram; timestamp filtering is applied locally.
`--limit`, `--after-id`, and `--after-timestamp` apply per chat regardless of how many
folders are being processed. Each folder's chats print under a `Folder: <name>` header,
so you always see exactly which chats a run actually queried as it happens.

Add `--ai-filter` to classify each message with Claude and print only the ones judged
relevant (event, task, important, or information — `ignore` results are hidden), with
extracted title/date/time/location/deadline/importance where available:

```bash
python -m app.main --folder "My Folder Name" --limit 10 --ai-filter
```

Each run prints a token-usage summary with an estimated cost at the end (`--ai-filter`
requires `ANTHROPIC_API_KEY`). Every message and its classification are saved to
`data/telegram_agent.db` (created automatically); running the same command again reuses
stored results instead of re-classifying, so repeat runs over overlapping message ranges
cost nothing extra. The summary reports how many messages were newly classified versus
reused from the database. `data/telegram_agent.db` contains your real message content and
is ignored by Git — never commit it.

### Customizing extraction with `template.md`

Copy `template.md.example` to `template.md` (gitignored — safe for personal context) to
give the AI extra guidance without touching code. Its content (minus the two structural
sections below) is appended to the system prompt for every message. Useful things to put
in it:

- **Locale** — a default timezone/locale for resolving ambiguous times.
- **Glossary** — group-specific abbreviations or jargon (e.g. venue codes, role names).
- **Priorities** — topics/activities that should be weighted as more important.
- **People to weight** — senders whose messages are usually official/authoritative.
- **Extra ignore rules** — additional patterns to auto-ignore beyond the default.
- **Style preferences** — summary length, or specific details to always surface
  (e.g. payment amounts, contact handles).

The base categories, required fields, and output schema always take priority over
anything in `template.md` — it can only add guidance, not override the schema.

Two sections are special: the app parses them structurally to control its own behavior,
and — since the AI never needs to see them and it would just waste tokens on every call —
they are stripped out before the rest of the file is sent as prompt guidance:

`## Folders to query` lists every folder to process when no `--chat`/`--folder` is given
on the command line, so you can monitor several folders without typing their names each
run, or comment one out (remove the bullet) to temporarily stop querying it:

```markdown
## Folders to query
- NUS Modules
- NUS CCAS
```

`## Ignored chats` entries (one per bullet, matched
as a case-insensitive substring) are skipped **before any AI call is made** — zero cost,
not just hidden output. An entry matches either a chat's display name (skips the whole
chat, before it's even fetched) or, for a chat that uses Telegram's forum/topics feature,
a topic's name (skips only messages in that topic, so other topics in the same chat still
get processed normally):

```markdown
## Ignored chats
E.g:
- Dinner
- Supper
```

### Model choice and cost

`--ai-filter` uses **Claude Sonnet 5** by default (`app/ai/processor.py`'s `MODEL`
constant). A side-by-side test against Claude Opus 5 and Haiku 4.5 on real messages found
Sonnet 5 matched Opus 5's classification accuracy at roughly half the cost, while Haiku
4.5 made real errors (a wrong relative-date calculation, and silently misclassifying an
actual task as `ignore`) — not worth the extra savings for a tool whose job is not missing
things. Change `MODEL` in `app/ai/processor.py` if you want to experiment further.

### Syncing to Notion (`--sync-notion`)

Add `--sync-notion` to create a Notion page for every AI result not yet synced:

```bash
python -m app.main --folder "My Folder Name" --ai-filter --sync-notion
```

It runs after any `--ai-filter` processing in the same invocation, and also picks up
anything left over from earlier runs — so it can be used **on its own**, with no
`--chat`/`--folder`, just to retry a sync that failed previously:

```bash
python -m app.main --sync-notion
```

One-time setup:

1. Create a Notion integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
   and copy its token into `NOTION_API_KEY`.
2. Create a database with these properties (Name/Title, Type/Select, Date/Date,
   Deadline/Date, Location/Text, Importance/Select, Source Chat/Text, Telegram Message
   ID/Text, Summary/Text, Status/Select, Created/Date) — or ask an assistant with Notion
   access to create it for you from this spec.
3. Share that database with your integration (`•••` menu → Connections → your integration).
4. Copy the database ID from its URL into `NOTION_DATABASE_ID`.

Each result becomes one page: `Type` is the classification (Event/Task/Important/
Information — `ignore` results are never synced), `Status` starts as "Not Started" for
you to update as you act on items. A result is matched to its Notion page via a local
`notion_sync` table, so a message's result is never synced twice even across separate
runs — a failed sync for one item is reported and skipped without blocking the rest of
the batch, and picked up again on the next `--sync-notion` run.

Notion's API (as of the `notion-client` v3.1.0 / Notion-Version `2025-09-03` used here)
creates pages under a database's *data source* ID, not the plain database ID shown in
its URL — the app resolves this automatically from `NOTION_DATABASE_ID` on each run.

## Running automatically once a day (optional, macOS)

`launchd/com.shantatei.tele-ai-agent.daily.plist` runs
`python -m app.main --ai-filter --sync-notion` once a day (7:00 AM by default) using
macOS's built-in scheduler, so you don't have to trigger it from a terminal yourself.
It relies on the 24-hour default lookback above, and on the Telegram session file
created during your first interactive login (`*.session`) — no login prompt should
appear on scheduled runs. To install it:

```bash
cp "launchd/com.shantatei.tele-ai-agent.daily.plist" ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.shantatei.tele-ai-agent.daily.plist
```

Output from each run is appended to `logs/launchd.log` (and errors to
`logs/launchd.err.log`) — check there if the Notion inbox or the desktop widget below
seem stale. To change the time, edit the `Hour`/`Minute` values in the `.plist`,
re-copy it, and reload:

```bash
launchctl bootout "gui/$(id -u)/com.shantatei.tele-ai-agent.daily" 2>/dev/null
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.shantatei.tele-ai-agent.daily.plist
```

To stop it running altogether: `launchctl bootout "gui/$(id -u)/com.shantatei.tele-ai-agent.daily"`.

## Desktop widget (optional, macOS)

`widget/` contains an [Übersicht](https://tracesof.net/uebersicht) desktop widget,
"Helix Pinboard", that shows upcoming events/tasks/deadlines straight from the Notion
inbox above — a lighter alternative to a full menu-bar app for glancing at what's
coming up. See [widget/README.md](widget/README.md) for install steps and how it works.

## First authentication

On the first run, Telethon will prompt in the terminal for your phone number and the
login code Telegram sends you. If you enabled two-step verification, it will also ask
for that password. Enter these prompts yourself; this application does not attempt to
bypass or automate Telegram's security checks. A local `.session` file is created so
later runs normally do not repeat the login.

## Test and basic static checks

```bash
python -m unittest discover -s tests -v
python -m compileall app tests
```

The unit tests use fake message objects and never need Telegram credentials or make
network calls.
