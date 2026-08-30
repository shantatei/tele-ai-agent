# Helix Pinboard — desktop widget

A small Übersicht widget showing upcoming events/tasks/deadlines from the Tele AI
Agent Notion inbox, styled as a dark-glass "pinboard" with a running cat as the
live/fetching indicator.

## Preview without installing anything

Open `widget/preview/index.html` directly in a browser (double-click it, or
`open widget/preview/index.html`) to see the design with sample data.

## Install the real widget

1. Install [Übersicht](https://tracesof.net/uebersicht) if you haven't already
   (free, one-click install).
2. Copy the whole `helix-pinboard.widget` folder into:
   ```
   ~/Library/Application Support/Übersicht/widgets/
   ```
   e.g.:
   ```bash
   cp -R "widget/helix-pinboard.widget" ~/Library/Application\ Support/Übersicht/widgets/
   ```
3. Übersicht picks up new widgets automatically (or use "Refresh All Widgets"
   from its menu-bar icon).

The widget calls `widget/fetch_events.py` in this project (via its absolute path,
using this project's own `.venv` and `.env`), so it always reads whatever is
currently in your Notion inbox — no separate setup needed beyond what Milestone 4
already configured (`NOTION_API_KEY` / `NOTION_DATABASE_ID` in `.env`).

## How it works

- Refreshes every 5 minutes (`refreshFrequency` in `index.jsx`).
- Shows every synced item, ordered by when the underlying Telegram message was
  actually sent (most recent first) — not by the event's own Date/Deadline, which
  can be far in the future or past. Scroll the board to see older ones.
- Clicking a card opens that item's Notion page.
- If Notion is unreachable or misconfigured, it shows an error message instead of
  crashing (see `fetch_events.py`'s `except` handling).

## Customizing

- **Position**: edit the `top` / `right` values at the top of `index.jsx`'s
  `className` export (currently pinned to the top-right of the screen).
- **Refresh rate**: `refreshFrequency` (milliseconds) in `index.jsx`.
- **Board height before it scrolls**: `max-height` on `.board` in `index.jsx`.
- **Colors/animations**: the rest of the `className` export in `index.jsx`.
