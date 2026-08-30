# tele-ai-agent

A personal pipeline that reads your Telegram chats, has Claude figure out what's
actually worth knowing, and keeps a running, de-duplicated log of it in Notion — plus
an optional macOS desktop widget so you can glance at it without opening anything.

## How it works

```text
Telegram → AI → SQLite → Notion
```

1. **Telegram** — authenticates a local Telegram account (Telethon) and retrieves
   messages from a single chat or every chat inside a Telegram folder, including
   Telegram's forum/topics feature.
2. **AI** — Claude classifies each message (event / task / important / information /
   ignore) and extracts structured details: title, summary, date, time, location,
   deadline, importance.
3. **SQLite** — every message and its classification is stored locally, so a message
   is never re-sent to the AI or re-synced to Notion once it's been processed.
4. **Notion** — each relevant result becomes a page in a Notion database, ready to
   browse, sort, or act on.

An optional desktop widget then reads straight from that Notion database to show
recent items on your desktop (see [Desktop widget](#desktop-widget-optional-macos)).

## Tech stack

<table>
<tr>
<td width="56"><img src="docs/assets/tech-stack/python.svg" width="36" height="36" alt="Python"></td>
<td><b>Python</b><br>Core language — glues every layer below together, no framework.</td>
</tr>
<tr>
<td><img src="docs/assets/tech-stack/telegram.svg" width="36" height="36" alt="Telegram"></td>
<td><b>Telegram API (Telethon)</b><br>Message source — auth, chats, folders, forum topics.</td>
</tr>
<tr>
<td><img src="docs/assets/tech-stack/claude.svg" width="36" height="36" alt="Claude"></td>
<td><b>Claude (Anthropic API)</b><br>Classifies and extracts structured detail from each message — Claude Sonnet 5.</td>
</tr>
<tr>
<td>🗄️</td>
<td><b>SQLite</b><br>Local persistence — dedup, processed-message tracking, restart/recovery.</td>
</tr>
<tr>
<td><img src="docs/assets/tech-stack/notion.svg" width="36" height="36" alt="Notion"></td>
<td><b>Notion API</b><br>Structured destination — the Telegram AI Inbox database.</td>
</tr>
<tr>
<td>🕐</td>
<td><b>launchd</b><br>macOS's built-in scheduler — can run the pipeline automatically once a day.</td>
</tr>
<tr>
<td><img src="docs/assets/tech-stack/react.svg" width="36" height="36" alt="React"></td>
<td><b>React (via Übersicht)</b><br>Optional desktop widget — see <a href="#desktop-widget-optional-macos">Desktop widget</a> below.</td>
</tr>
</table>

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
(get one at [console.anthropic.com](https://console.anthropic.com)). `NOTION_API_KEY`
and `NOTION_DATABASE_ID` are only required if you use `--sync-notion` — see
[Syncing to Notion](#syncing-to-notion---sync-notion) below for setup. `.env` and the
generated Telethon session file are ignored by Git.

## Usage

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

Messages are printed oldest to newest after the optional filters are applied. Each
folder's chats print under a `Folder: <name>` header, so you always see exactly which
chats a run actually queried as it happens.

Add `--ai-filter` to classify each message with Claude and print only the ones judged
relevant (event, task, important, or information — `ignore` results are hidden), with
extracted title/date/time/location/deadline/importance where available:

```bash
python -m app.main --folder "My Folder Name" --limit 10 --ai-filter
```

Each run prints a token-usage summary with an estimated cost at the end. Every message
and its classification are saved to `data/telegram_agent.db` (created automatically);
running the same command again reuses stored results instead of re-classifying, so
repeat runs over overlapping message ranges cost nothing extra. `data/telegram_agent.db`
contains your real message content and is ignored by Git — never commit it.

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
and they are stripped out before the rest of the file is sent as prompt guidance (the
AI never needs to see them):

`## Folders to query` lists every folder to process when no `--chat`/`--folder` is given
on the command line:

```markdown
## Folders to query
- Study Group
- Sports Club
```

`## Ignored chats` entries (one per bullet, matched as a case-insensitive substring)
are skipped **before any AI call is made** — zero cost, not just hidden output. An
entry matches either a chat's display name, or, for a chat that uses Telegram's
forum/topics feature, a topic's name (skips only that topic, not the whole chat):

```markdown
## Ignored chats
- Dinner
- Supper
```

### Model choice and cost

`--ai-filter` uses **Claude Sonnet 5** by default (`app/ai/processor.py`'s `MODEL`
constant) — a good balance of classification accuracy and cost for this kind of task.
Change `MODEL` there if you want to experiment with a different model.

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
   ID/Text, Summary/Text, Status/Select, Created/Date).
3. Share that database with your integration (`•••` menu → Connections → your integration).
4. Copy the database ID from its URL into `NOTION_DATABASE_ID`.

Each result becomes one page: `Type` is the classification, `Status` starts as "Not
Started" for you to update as you act on items, and `Created` holds the original
Telegram message's timestamp. A result is never synced twice, even across separate
runs; a failed sync for one item is reported and skipped without blocking the rest of
the batch, and retried on the next `--sync-notion` run. The database's own description
(shown under its title in Notion) is updated with a "Last synced: ..." timestamp
(Singapore time) after every sync.

## Running it automatically once a day (optional, macOS)

`launchd/com.tele-ai-agent.daily.plist` runs the equivalent of
`python -m app.main --ai-filter --sync-notion` once a day (7:00 AM by default) via
macOS's built-in scheduler, so you don't have to trigger it from a terminal yourself.
Install it with:

```bash
cp "launchd/com.tele-ai-agent.daily.plist" ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.tele-ai-agent.daily.plist
```

Output from each run is appended to `logs/launchd.log` (and errors to
`logs/launchd.err.log`) inside the project directory.

## Desktop widget (optional, macOS)

`widget/` contains an [Übersicht](https://tracesof.net/uebersicht) desktop widget
that shows recent items straight from the Notion inbox above — a lighter alternative
to a full menu-bar app for glancing at what's going on. Its display name is a one-line
edit in the widget's own file, so you can call it whatever you like. See
[widget/README.md](widget/README.md) for install steps and how it works.

## First authentication

On the first run, Telethon will prompt in the terminal for your phone number and the
login code Telegram sends you. If you enabled two-step verification, it will also ask
for that password. Enter these prompts yourself; this application does not attempt to
bypass or automate Telegram's security checks. A local `.session` file is created so
later runs normally do not repeat the login.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall app tests
```

The unit tests use fake message objects and never need Telegram credentials or make
network calls.
