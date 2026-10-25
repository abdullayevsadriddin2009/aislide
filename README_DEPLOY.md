# Render deployment guide

## 1. Prepare the repository

1. Create a private Git repository.
2. Upload the source files, but do not upload `.env`, SQLite database files, or generated documents.
3. Confirm the repository uses the updated `.gitignore`.

## 2. Create the web service

1. In Render, create a Web Service connected to the repository.
2. Let Render read `render.yaml`.
3. Set the following environment variables in the Render dashboard:
   - `BOT_TOKEN` — fresh Telegram token from BotFather.
   - `ADMIN_ID` — administrator's Telegram ID.
   - `AI_BASE_URL` — verified compatible AI endpoint, for example `https://openrouter.ai/api/v1`.
   - `AI_API_KEY` — key for that endpoint.
   - `WEB_ADMIN_PASSWORD` — unique and strong password.
   - `WEB_ADMIN_SECRET_KEY` — a long random value, separate from the AI key.
4. Deploy and review the logs.

## 3. SQLite persistence

A normal ephemeral service filesystem is not a safe place to keep production balances and orders. If the selected Render plan supports persistent disks, attach one and set `DATA_DIR` to the exact mount path. Otherwise, use a managed database. Verify data survives a new deploy before accepting real payments.

## 4. PDF support

The build configuration installs LibreOffice. PDF output should be tested after deployment; if conversion fails, the bot falls back to sending a DOCX instead of falsely naming it a PDF.

## 5. Verify the deployment

- Open the Render service URL and confirm the health endpoint responds.
- Send `/start` to the Telegram bot.
- Test one presentation in each design and one document in the target language.
- Test an invalid AI key to confirm localized fallback output is still usable.
- Do not switch to paid mode until balance changes, duplicate callbacks, failed generation, refunds, and database persistence have been tested.

## Secret rotation

If an earlier project copy contained hard-coded bot or AI credentials, revoke and replace them before deployment. Do not paste secrets into GitHub commits, chat messages, or public issue trackers.
