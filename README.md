# Telegram MTProto Userbot

A production-ready Telegram userbot that operates as a **real user account** via MTProto (NOT the Bot API). Powered by AI (OpenAI/Claude) with human behavior simulation to appear natural.

## Features

- **MTProto Client** — Uses Telethon to connect as a real Telegram user
- **AI Responses** — Integrates with OpenAI (GPT-4o) or Anthropic (Claude) for intelligent, contextual replies
- **Human Behavior Simulation** — Randomized delays, typing indicators, occasional non-responses, and time-of-day awareness
- **Smart Triggers** — Only responds to DMs, @mentions, or keyword matches (not every message)
- **Rate Limiting** — Per-chat, per-user cooldowns and global rate limits to prevent spam
- **Memory Store** — SQLite-backed conversation history and user profiling
- **Command System** — Owner-only commands for pausing, checking stats, ignoring users, etc.
- **Session Persistence** — Login once, run forever without re-authentication

## Architecture

```
app/
├── ai/          # LLM integration (OpenAI, Anthropic)
├── behavior/    # Human simulation (delays, typing, ignore logic)
├── client/      # Telegram MTProto connection (Telethon)
├── commands/    # Owner command system (!ping, !stats, !pause, etc.)
├── config/      # Settings loaded from environment variables
├── handlers/    # Message processing and trigger logic
├── memory/      # SQLite conversation history & user profiles
├── utils/       # Logging, rate limiting
└── main.py      # Application entry point
```

## Quick Start

### Prerequisites

- Python 3.10+
- Telegram API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
- An OpenAI or Anthropic API key

### 1. Clone & Install

```bash
git clone <repo-url>
cd telegram-userbot

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install .
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your_api_hash_here
TELEGRAM_PHONE=+1234567890

AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

### 3. Run

```bash
python run.py
```

On first run, you'll be prompted to enter the Telegram verification code sent to your phone. After successful login, the session is saved and subsequent runs won't require re-authentication.

## Docker Deployment

### First Run (Interactive — for phone auth)

```bash
docker compose run --rm userbot
```

Enter the verification code when prompted. The session file is saved to `./sessions/`.

### Subsequent Runs (Background)

```bash
docker compose up -d
```

### View Logs

```bash
docker compose logs -f userbot
```

## Configuration

All settings are configured via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_API_ID` | — | Telegram API ID |
| `TELEGRAM_API_HASH` | — | Telegram API Hash |
| `TELEGRAM_PHONE` | — | Phone number for login |
| `AI_PROVIDER` | `openai` | `openai` or `anthropic` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ANTHROPIC_API_KEY` | — | Anthropic API key |
| `PERSONALITY_PROMPT` | (friendly chat) | System prompt defining personality |
| `MIN_RESPONSE_DELAY` | `3` | Minimum response delay (seconds) |
| `MAX_RESPONSE_DELAY` | `25` | Maximum response delay (seconds) |
| `IGNORE_RATE` | `0.15` | Probability of ignoring a message |
| `TRIGGER_KEYWORDS` | `hey,help,question,ask` | Keywords that trigger responses |
| `RESPOND_TO_DM` | `true` | Respond to direct messages |
| `RESPOND_TO_MENTIONS` | `true` | Respond to @mentions |
| `RATE_LIMIT_PER_CHAT` | `5` | Max messages per minute per chat |
| `USER_COOLDOWN_SECONDS` | `30` | Cooldown between responses to same user |
| `GLOBAL_RATE_LIMIT` | `20` | Max messages per minute globally |
| `ACTIVE_HOURS_START` | `8` | Start of active hours (UTC) |
| `ACTIVE_HOURS_END` | `23` | End of active hours (UTC) |

## Owner Commands

Send these commands (prefixed with `!`) from your own account:

| Command | Description |
|---|---|
| `!ping` | Check bot status and uptime |
| `!stats` | Show message/user/response statistics |
| `!contacts [N]` | Show top N frequent contacts |
| `!status` | Show current bot configuration |
| `!pause` | Pause automatic responses |
| `!resume` | Resume automatic responses |
| `!ignore <id>` | Add chat/user to ignore list |
| `!unignore <id>` | Remove from ignore list |
| `!help` | Show all commands |

## How It Works

### Trigger Logic

The bot does NOT respond to every message. It responds when:

1. **Direct message** — Someone DMs you (configurable)
2. **@mention** — Someone mentions your @username in a group
3. **Keyword match** — Message contains one of the configured trigger keywords

### Human Behavior Simulation

To appear natural, the bot:

- **Delays responses** using a beta distribution (3–25 seconds, skewed toward shorter delays)
- **Shows typing indicators** proportional to response length
- **Randomly ignores** 10–30% of messages
- **Avoids repetition** by tracking recent responses
- **Reduces activity** outside configured active hours

### Conversation Context

Each response includes the last N messages from the same chat, giving the AI context for coherent conversations.

## VPS Deployment

### Using systemd

Create `/etc/systemd/system/telegram-userbot.service`:

```ini
[Unit]
Description=Telegram MTProto Userbot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram-userbot
ExecStart=/home/ubuntu/telegram-userbot/.venv/bin/python run.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/telegram-userbot/.env

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-userbot
sudo systemctl start telegram-userbot
```

## License

MIT
