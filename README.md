# Talaba AI Slide Bot

Telegram bot for creating academic documents and PowerPoint presentations. The current source has 9 active services: presentation, report, independent assignment, coursework, diploma work, essay, test, article, and thesis/abstract.

## Main features

- 6 supported output languages: Uzbek, Russian, English, Turkish, German, and French.
- Presentation generator with 3 separate designs: Timurid navy/gold, scientific green, and minimal premium.
- Presentation slide count is selected separately from the design. All 3 styles support 5, 7, 10, 12, 15, 18, 20, 25, and 30 slides.
- Presentations include a cover, localized agenda, body slides, and final summary/thanks slide.
- DOCX templates use academic page layout and localized headings. PDF export uses LibreOffice when installed.
- Required service options are requested before creation: page/word/question count, output language, title-page information when applicable, author, format, and presentation design.
- Balance, referrals, Telegram admin tools, and a web-admin panel.

## Setup

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your own values. Do not commit `.env` or upload it to a public repository.

Required configuration:

- `BOT_TOKEN` — a fresh Telegram bot token from BotFather.
- `ADMIN_ID` — Telegram numeric ID of the bot administrator.
- `AI_BASE_URL` and `AI_API_KEY` — a valid compatible AI endpoint and its key.
- `WEB_ADMIN_PASSWORD` — a strong, unique web-admin password.
- `WEB_ADMIN_SECRET_KEY` — a long, random secret, different from the AI API key.

Then run the generator smoke tests and start the bot:

```bash
python -m unittest discover -s tests -v
python run.py
```

If `BOT_TOKEN` is empty, the bot deliberately does not start. Configure credentials before running it.

## Deployment notes

- On Render, configure environment variables in the service dashboard. Never put tokens in source code.
- SQLite files are not persistent on a typical ephemeral service filesystem. Attach a persistent disk and set `DATA_DIR` to its mount path, or move to a managed database before relying on production balances/orders.
- PDF conversion requires LibreOffice on Linux. If it is unavailable, the bot may return the DOCX version instead.
- For bot API providers, use an endpoint and key that you control and have verified. Do not assume every OpenAI-compatible service supports the same request format.

## Security

Credentials that were hard-coded in an older copy of this project should be treated as exposed. Revoke and rotate those values through Telegram/AI provider dashboards before deploying this version. The new source intentionally does not include active credentials.
