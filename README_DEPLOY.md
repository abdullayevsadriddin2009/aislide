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
   - `WEBAPP_URL` — the public HTTPS address of this service, for example `https://ai-slide-bot.onrender.com`.
     On Render the value is taken from `RENDER_EXTERNAL_URL` automatically; set it explicitly if you use a custom domain.
4. Deploy and review the logs.

## 2b. Telegram Mini App

The bot serves a Mini App from the same web service, so no extra hosting is required.

1. After the first deploy, open `https://<your-service>/app` — the page must load
   (outside Telegram it only shows the "open inside Telegram" note).
2. `WEBAPP_URL` must be the same HTTPS origin. Without it the Mini App buttons stay hidden.
   `SLIDE_IMAGES=0` (default) keeps bot and Mini App decks identical: no stock photos.
   Set `1` if you want one topic-searched photo per slide in both.
3. On startup the bot sets the chat menu button (default label “Ilova”, override with
   `MINI_APP_TEXT`) next to the message field and adds `/app` to the command list, so users
   open the app with one tap.
4. In BotFather run `/mybots` → your bot → **Bot Settings → Menu Button → Configure menu button**,
   paste the same `https://<your-service>/app` URL. Telegram then shows the **Open** button in the
   chat list and in the chat header — exactly the entry point other Mini Apps have.
   (`/setmenubutton` and **Bot Settings → Configure Mini App** set the same value.)
5. Telegram requires a verified HTTPS certificate, so use the Render domain or a custom domain — not an IP.
6. Files created in the Mini App are copied to `DATA_DIR/files/` and linked to the order, so an
   order can be downloaded again at any time (the temporary copy in `DATA_DIR/mini/` expires
   after three hours). Orders created before this version have no stored file and only offer
   "Qayta yaratish".
7. Attach a persistent disk to `DATA_DIR` if downloads must survive a redeploy; on an ephemeral
   filesystem `DATA_DIR/files/` is cleared when the service is rebuilt.

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
