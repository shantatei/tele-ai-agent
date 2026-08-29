// Helix Pinboard — shows upcoming events/tasks from the Tele AI Agent Notion inbox.
// Install: copy this whole "helix-pinboard.widget" folder into
// ~/Library/Application Support/Übersicht/widgets/

export const command =
  'cd "/Users/shantatei/Documents/Personal Projects/Telegram AI Agent" && .venv/bin/python widget/fetch_events.py';

export const refreshFrequency = 300000; // 5 minutes

const CATEGORY = {
  Event: { color: "#e8a33d", icon: "◆" }, // ◆
  Task: { color: "#5fa8a0", icon: "✓" }, // ✓
  Important: { color: "#e2634f", icon: "!" },
  Information: { color: "#8b87a6", icon: "i" },
};

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

// Parses a bare "YYYY-MM-DD" as a local date (avoids the UTC-midnight shift that
// `new Date("YYYY-MM-DD")` can introduce).
function formatDate(isoDate) {
  if (!isoDate) return null;
  const [y, m, d] = isoDate.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return `${WEEKDAYS[dt.getDay()]}, ${MONTHS[m - 1]} ${d}`;
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function EventCard({ event, index }) {
  const cat = CATEGORY[event.type] || CATEGORY.Information;
  const tilt = index % 2 === 0 ? "-0.5deg" : "0.5deg";
  const delay = `${0.05 + index * 0.08}s`;
  const isDeadline = !event.date && event.deadline;

  return (
    <a
      className="card"
      href={event.url}
      style={{ "--tag-color": cat.color, "--tilt": tilt, "--delay": delay }}
    >
      <div className="card-icon">{cat.icon}</div>
      <div className="card-body">
        <div className="card-title">{event.name}</div>
        {event.date && (
          <div className="card-meta">{formatDate(event.date)}</div>
        )}
        {isDeadline && (
          <div className="card-meta">Due {formatDate(event.deadline)}</div>
        )}
        {event.sourceChat && <div className="card-chat">{event.sourceChat}</div>}
      </div>
    </a>
  );
}

export const render = ({ output }) => {
  let data = null;
  let parseError = null;
  try {
    data = JSON.parse(output || "{}");
  } catch (e) {
    parseError = "Could not read widget data.";
  }

  const events = (data && data.events) || [];
  const errorMessage = (data && data.error) || parseError;
  const updatedLabel = errorMessage
    ? "error"
    : `Updated ${formatTime(new Date())}`;

  return (
    <div className="widget">
      <div className="masthead">
        <div>
          <div className="masthead-title-row">
            <div className="masthead-badge">{"🧬"}</div>
            <div className="masthead-title">Helix Pinboard</div>
          </div>
          <div className="masthead-sub">from Telegram, via Notion</div>
        </div>
        <div className="live-status">
          <span className={errorMessage ? "live-dot live-dot-error" : "live-dot"} />
          {updatedLabel}
        </div>
      </div>

      {errorMessage ? (
        <div className="empty-state">{errorMessage}</div>
      ) : events.length === 0 ? (
        <div className="empty-state">No upcoming events or deadlines.</div>
      ) : (
        <div className="board">
          {events.map((event, i) => (
            <EventCard event={event} index={i} key={event.url} />
          ))}
        </div>
      )}

      <div className="footer-hint">
        refreshes every 5 min &middot; click a card to open it in Notion
      </div>

      <div className="cat-track">
        <div className="cat-mover">
          <div className="cat-gif" />
        </div>
      </div>
    </div>
  );
};

export const className = `
  top: 40px;
  right: 40px;
  width: 340px;

  font-family: "Karla", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #f2efe9;

  .widget {
    background: rgba(28, 26, 34, 0.62);
    -webkit-backdrop-filter: blur(28px) saturate(140%);
    backdrop-filter: blur(28px) saturate(140%);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 18px;
    padding: 18px 16px 16px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3), 0 8px 24px -8px rgba(0, 0, 0, 0.55);
    box-sizing: border-box;
  }

  * { box-sizing: border-box; }

  .masthead {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 2px 14px;
    margin-bottom: 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  }

  .masthead-title-row {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .masthead-badge {
    width: 22px;
    height: 22px;
    border-radius: 7px;
    background: linear-gradient(135deg, #e8a33d, #c97f22);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    flex-shrink: 0;
  }

  .masthead-title {
    font-family: Georgia, "Times New Roman", serif;
    font-size: 16.5px;
    font-weight: 600;
    letter-spacing: 0.01em;
  }

  .masthead-sub {
    font-size: 10.5px;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: #726a60;
    margin-top: 1px;
  }

  .live-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10.5px;
    color: #a79e93;
    font-variant-numeric: tabular-nums;
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #5fa8a0;
    box-shadow: 0 0 0 0 rgba(95, 168, 160, 0.55);
    animation: pulse 2.4s ease-out infinite;
  }

  .live-dot-error {
    background: #e2634f;
    box-shadow: none;
    animation: none;
  }

  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0 rgba(95, 168, 160, 0.55); }
    70%  { box-shadow: 0 0 0 6px rgba(95, 168, 160, 0); }
    100% { box-shadow: 0 0 0 0 rgba(95, 168, 160, 0); }
  }

  .empty-state {
    padding: 18px 4px;
    font-size: 12px;
    color: #a79e93;
    text-align: center;
  }

  .board {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .card {
    position: relative;
    display: flex;
    gap: 10px;
    padding: 10px 12px 10px 13px;
    background: rgba(255, 255, 255, 0.055);
    border: 1px solid rgba(255, 255, 255, 0.09);
    border-radius: 12px;
    text-decoration: none;
    color: inherit;
    cursor: pointer;
    opacity: 0;
    transform: translateY(10px) rotate(var(--tilt, 0deg));
    animation: pin-in 0.55s cubic-bezier(0.2, 0.9, 0.3, 1) forwards;
    animation-delay: var(--delay, 0s);
    transition: background 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
  }

  .card::before {
    content: "";
    position: absolute;
    left: 0;
    top: 10px;
    bottom: 10px;
    width: 3px;
    border-radius: 3px;
    background: var(--tag-color, #8b87a6);
  }

  .card:hover {
    background: rgba(255, 255, 255, 0.09);
    transform: translateY(-2px) rotate(0deg);
    box-shadow: 0 10px 22px -10px rgba(0, 0, 0, 0.6);
  }

  @keyframes pin-in {
    0%   { opacity: 0; transform: translateY(10px) rotate(var(--tilt, 0deg)) scale(0.97); }
    60%  { opacity: 1; }
    100% { opacity: 1; transform: translateY(0) rotate(var(--tilt, 0deg)) scale(1); }
  }

  .card-icon {
    flex-shrink: 0;
    width: 26px;
    height: 26px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--tag-color, #8b87a6) 22%, transparent);
    color: var(--tag-color, #8b87a6);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    margin-top: 1px;
  }

  .card-body { min-width: 0; flex: 1; }

  .card-title {
    font-size: 13px;
    font-weight: 600;
    line-height: 1.3;
    color: #f2efe9;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-meta {
    margin-top: 3px;
    font-size: 11px;
    color: #a79e93;
    font-variant-numeric: tabular-nums;
  }

  .card-chat {
    font-size: 10px;
    color: #726a60;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .footer-hint {
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.09);
    font-size: 10px;
    color: #726a60;
    text-align: center;
    letter-spacing: 0.02em;
  }

  .cat-track {
    position: relative;
    height: 30px;
    margin-top: 4px;
    overflow: hidden;
  }

  .cat-mover {
    position: absolute;
    bottom: 0;
    left: -20%;
    width: 46px;
    height: 34px;
    animation: cat-dash 4.6s linear infinite;
  }

  @keyframes cat-dash {
    from { left: -20%; }
    to   { left: 112%; }
  }

  .cat-gif {
    width: 100%;
    height: 100%;
    background-image: url('assets/running-cat-transparent.gif');
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center bottom;
    filter: drop-shadow(0 3px 2px rgba(0, 0, 0, 0.5));
  }

  @media (prefers-reduced-motion: reduce) {
    .card { animation: none; opacity: 1; transform: none; }
    .live-dot { animation: none; }
    .cat-track { display: none; }
  }
`;
