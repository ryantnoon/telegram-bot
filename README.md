# Telegram AI Bot

A Telegram bot that responds to messages using Claude (Anthropic). Runs as an always-on process on Fly.io's free tier.

## Features

- Real-time responses via long polling
- Per-user conversation history (last 20 messages)
- `/start` — Welcome message
- `/clear` — Reset conversation history
- Configurable system prompt and model

## Prerequisites

1. **Telegram Bot Token** — You already have this (`@NoonPerplexity_Bot`)
2. **Anthropic API Key** — Sign up at [console.anthropic.com](https://console.anthropic.com), add a credit card, and create an API key. Usage is pay-as-you-go (~$0.01-0.50/month for personal chat).
3. **Fly.io CLI** — Install below

## Deploy to Fly.io (5 minutes)

### 1. Install Fly CLI

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

### 2. Sign up / Log in

```bash
fly auth signup
# or if you already have an account:
fly auth login
```

### 3. Launch the app

From this project directory:

```bash
fly launch
```

When prompted:
- **App name**: `noon-telegram-bot` (or whatever you prefer)
- **Region**: Pick the closest to you (e.g., `ewr` for Newark/East Coast)
- **Would you like to set up a PostgreSQL database?** → No
- **Would you like to set up an Upstash Redis database?** → No
- **Would you like to deploy now?** → No (we need to set secrets first)

### 4. Set your secrets

```bash
fly secrets set TELEGRAM_BOT_TOKEN="8713811186:AAHBxIkbB-mhk0JESsN8lVn7CREwL3EQyv4"
fly secrets set ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

Optional overrides:
```bash
fly secrets set ANTHROPIC_MODEL="claude-sonnet-4-20250514"
fly secrets set SYSTEM_PROMPT="You are a sarcastic but helpful assistant."
fly secrets set MAX_HISTORY="30"
```

### 5. Deploy

```bash
fly deploy
```

That's it. The bot will start polling for messages immediately.

### 6. Verify it's running

```bash
fly logs
```

You should see:
```
Bot starting up...
Webhook cleared: {'ok': True, ...}
Listening for messages...
```

Send a message to your bot on Telegram — it should respond within seconds.

## Managing the Bot

```bash
# View live logs
fly logs

# Restart the bot
fly apps restart noon-telegram-bot

# Stop the bot
fly scale count 0

# Start it again
fly scale count 1

# Update after code changes
fly deploy

# Check status
fly status
```

## Cost

- **Fly.io**: Free for a single shared-cpu-1x 256MB VM (well within their soft free tier)
- **Anthropic API**: ~$3/million input tokens, ~$15/million output tokens. For casual personal use, expect < $1/month. Use `claude-3-haiku-20240307` as the model for even cheaper responses.

## Customization

Edit these environment variables via `fly secrets set`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | (required) | Your bot token from BotFather |
| `ANTHROPIC_API_KEY` | (required) | Your Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `SYSTEM_PROMPT` | General assistant | Bot personality/instructions |
| `MAX_HISTORY` | `20` | Messages to keep per conversation |
