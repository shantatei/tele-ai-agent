# Tele AI Agent — Phase 1, Step 1

This is the first, deliberately small part of Tele AI Agent. The eventual flow is:

```text
Telegram → AI → SQLite → Notion
```

This repository implements only **Telegram → Terminal**. It authenticates a local
Telegram account, retrieves messages from a single chat or every chat inside a
Telegram folder, returns structured message data inside the reader module, and
prints that data in the terminal. It contains no AI, database, Notion, or
menu-bar functionality.

## Progress so far

- [x] Authenticate a local Telegram account (Telethon, interactive phone/code login)
- [x] Read messages from a single chat by username, numeric ID, or invite link
- [x] Read messages from every chat inside a named Telegram folder
- [x] Filter messages by minimum message ID and/or timestamp
- [x] Print structured message data to the terminal
- [ ] AI classification/extraction layer (Milestone 2 — not started)

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
```

`TELEGRAM_TEST_CHAT` can be a username, a numeric ID, or an invite link that your
account can access. `.env` and the generated Telethon session file are ignored by Git.

## Run

With the virtual environment active:

```bash
python -m app.main
```

Override the configured chat or narrow the messages if useful:

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

Messages are printed oldest to newest after the optional filters are applied. The
message-ID filter is delegated to Telegram; timestamp filtering is applied locally.
`--limit`, `--after-id`, and `--after-timestamp` apply per chat when using `--folder`.

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
