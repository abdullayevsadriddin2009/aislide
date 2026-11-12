"""Web admin panel — Flask based. Starts with the bot. English UI."""
import sqlite3
import threading
import secrets
import html
from flask import Flask, request, session, redirect, render_template_string, url_for
import config

app = Flask(__name__)
app.secret_key = config.WEB_ADMIN_SECRET_KEY or secrets.token_hex(32)

# Telegram Mini App: /app sahifasi va /api/mini/* endpointlari.
try:
    from mini_app import mini as mini_app_blueprint
    app.register_blueprint(mini_app_blueprint)
except Exception as _mini_err:  # Mini App yuklanmasa bot baribir ishlaydi
    print(f"[mini_app] yuklanmadi: {_mini_err}", flush=True)

@app.route("/health")
def health():
    """Cron / UptimeRobot uchun — bot tirikligini tekshirish. Login shart emas."""
    return "OK", 200

PAGE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin Panel — AI Slide Bot</title>
<style>
body{font-family:system-ui,sans-serif;background:#f5f6fa;margin:0;padding:20px;color:#222}
h1{color:#2c3e50}
.card{background:#fff;border-radius:12px;padding:20px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.stat{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:18px;border-radius:12px;text-align:center}
.stat .num{font-size:28px;font-weight:bold}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{padding:8px 10px;border-bottom:1px solid #eee;text-align:left;font-size:14px}
th{background:#f0f2f5}
.btn{background:#e74c3c;color:#fff;border:none;padding:8px 14px;border-radius:6px;cursor:pointer;text-decoration:none;display:inline-block}
.btn.green{background:#27ae60}
input,textarea{width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:6px;box-sizing:border-box}
.nav a{margin-right:14px;color:#764ba2;text-decoration:none;font-weight:600}
.badge{padding:3px 8px;border-radius:10px;font-size:12px;color:#fff}
.b-pending{background:#f39c12}.b-approved{background:#27ae60}.b-rejected{background:#e74c3c}
</style></head><body>
<h1>👑 AI Slide Bot — Admin Panel</h1>
<div class="nav"><a href="/">Dashboard</a><a href="/users">Users</a><a href="/orders">Orders</a><a href="/checks">Receipts</a><a href="/ai">AI chat</a><a href="/settings">Settings</a><a href="/logout">Logout</a></div>
{{content|safe}}
</body></html>
"""

def q(sql, args=()):
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.execute(sql, args)
    rows = cur.fetchall()
    con.commit()
    con.close()
    return rows

def login_required():
    return session.get("admin") == "1"

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if config.WEB_ADMIN_PASSWORD and request.form.get("password") == config.WEB_ADMIN_PASSWORD:
            session["admin"] = "1"
            return redirect("/")
        return "❌ Wrong password"
    return PAGE.replace("{{content|safe}}",
        '<div class="card"><h2>Login</h2><form method="post"><input type="password" name="password" placeholder="Password"><button class="btn green">Login</button></form></div>')

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    if not login_required(): return redirect("/login")
    users = q("SELECT COUNT(*) c FROM users")[0]["c"]
    total_bal = q("SELECT COALESCE(SUM(balance),0) s FROM users")[0]["s"]
    orders = q("SELECT COUNT(*) c FROM orders")[0]["c"]
    checks = q("SELECT COUNT(*) c FROM checks WHERE status='pending'")[0]["c"]
    content = f"""
    <div class="grid">
      <div class="stat"><div class="num">{users}</div>Users</div>
      <div class="stat"><div class="num">{total_bal}</div>Total balance (so'm)</div>
      <div class="stat"><div class="num">{orders}</div>Orders</div>
      <div class="stat"><div class="num">{checks}</div>Pending receipts</div>
    </div>
    <div class="card"><h3>Recent orders</h3><table><tr><th>ID</th><th>User</th><th>Service</th><th>Topic</th><th>Price</th><th>Date</th></tr>
    {''.join(f"<tr><td>{html.escape(str(o['id']))}</td><td>{html.escape(str(o['user_id']))}</td><td>{html.escape(str(o['service']))}</td><td>{html.escape(str(o['topic'] or '')[:40])}</td><td>{html.escape(str(o['price']))}</td><td>{html.escape(str(o['created_at']))}</td></tr>" for o in q("SELECT * FROM orders ORDER BY id DESC LIMIT 10"))}
    </table></div>"""
    return PAGE.replace("{{content|safe}}", content)

@app.route("/users")
def users():
    if not login_required(): return redirect("/login")
    rows = q("SELECT * FROM users ORDER BY created_at DESC LIMIT 200")
    content = '<div class="card"><h3>Users (last 200)</h3><table><tr><th>ID</th><th>Username</th><th>Name</th><th>Lang</th><th>Balance</th><th>Bonus</th><th>Referred by</th></tr>'
    for u in rows:
        content += f"<tr><td>{html.escape(str(u['telegram_id']))}</td><td>@{html.escape(str(u['username'] or '-'))}</td><td>{html.escape(str(u['first_name'] or '-'))}</td><td>{html.escape(str(u['lang']))}</td><td>{html.escape(str(u['balance']))}</td><td>{html.escape(str(u['bonus_balance']))}</td><td>{html.escape(str(u['referred_by'] or '-'))}</td></tr>"
    content += "</table></div>"
    return PAGE.replace("{{content|safe}}", content)

@app.route("/orders")
def orders():
    if not login_required(): return redirect("/login")
    rows = q("SELECT * FROM orders ORDER BY id DESC LIMIT 200")
    content = '<div class="card"><h3>Orders</h3><table><tr><th>ID</th><th>User</th><th>Service</th><th>Topic</th><th>Price</th><th>Status</th></tr>'
    for o in rows:
        content += f"<tr><td>{html.escape(str(o['id']))}</td><td>{html.escape(str(o['user_id']))}</td><td>{html.escape(str(o['service']))}</td><td>{html.escape(str(o['topic'] or '')[:50])}</td><td>{html.escape(str(o['price']))}</td><td>{html.escape(str(o['status']))}</td></tr>"
    content += "</table></div>"
    return PAGE.replace("{{content|safe}}", content)

@app.route("/checks")
def checks():
    if not login_required(): return redirect("/login")
    rows = q("SELECT * FROM checks ORDER BY id DESC LIMIT 100")
    content = '<div class="card"><h3>Payment Receipts</h3><table><tr><th>ID</th><th>User</th><th>Amount</th><th>Status</th><th>Action</th></tr>'
    for c in rows:
        safe_status = html.escape(str(c["status"]))
        badge = f'<span class="badge b-{safe_status}">{safe_status}</span>'
        actions = ""
        if c["status"] == "pending":
            actions = f'<a class="btn green" href="/check/{c["id"]}/approve">Approve</a> <a class="btn" href="/check/{c["id"]}/reject">Reject</a>'
        content += f"<tr><td>{c['id']}</td><td>{c['user_id']}</td><td>{c['amount']}</td><td>{badge}</td><td>{actions}</td></tr>"
    content += "</table></div>"
    return PAGE.replace("{{content|safe}}", content)

@app.route("/check/<int:cid>/<action>")
def check_action(cid, action):
    if not login_required(): return redirect("/login")
    c = q("SELECT * FROM checks WHERE id=?", (cid,))
    if c and c[0]["status"] == "pending":
        st = "approved" if action == "approve" else "rejected"
        q("UPDATE checks SET status=? WHERE id=?", (st, cid))
        if action == "approve":
            q("UPDATE users SET balance=balance+? WHERE telegram_id=?", (c[0]["amount"], c[0]["user_id"]))
    return redirect("/checks")

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if not login_required(): return redirect("/login")
    if request.method == "POST":
        for k in ("referral_percent", "payment_info", "free_mode"):
            v = request.form.get(k)
            if v is not None:
                q("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (k, v))
        return redirect("/settings")
    ref = q("SELECT value FROM settings WHERE key='referral_percent'")
    pay = q("SELECT value FROM settings WHERE key='payment_info'")
    free = q("SELECT value FROM settings WHERE key='free_mode'")
    ref_value = html.escape(str(ref[0]['value'] if ref else '10'), quote=True)
    pay_value = html.escape(str(pay[0]['value'] if pay else ''))
    free_value = html.escape(str(free[0]['value'] if free else '1'), quote=True)
    content = f"""<div class="card"><h3>Settings</h3><form method="post">
    <label>Referral percent:</label><input name="referral_percent" value="{ref_value}">
    <label>Payment info:</label><textarea name="payment_info" rows="4">{pay_value}</textarea>
    <label>Mode (1=free, 0=paid):</label><input name="free_mode" value="{free_value}">
    <button class="btn green">Save</button></form></div>"""
    return PAGE.replace("{{content|safe}}", content)

def _ai_page_content():
    """AI kalitlari, modellari va chat sozlamalari sahifasi."""
    import ai_pool
    esc = lambda value: html.escape(str(value if value is not None else ""), quote=True)
    keys = ai_pool.keys()
    models = ai_pool.models()

    key_rows = ""
    for key in keys:
        state = "active" if key["active"] else "off"
        key_rows += (
            f"<tr><td>{esc(key['label'] or '-')}</td><td>{esc(key['provider'])}</td>"
            f"<td><code>{esc(ai_pool.mask(key['api_key']))}</code></td>"
            f"<td>{int(key['fails'])}</td><td>{state}</td><td>"
            f"<form method='post' style='display:inline'><input type='hidden' name='action' value='toggle_key'>"
            f"<input type='hidden' name='id' value='{int(key['id'])}'>"
            f"<button class='btn green'>{'Disable' if key['active'] else 'Enable'}</button></form> "
            f"<form method='post' style='display:inline'><input type='hidden' name='action' value='del_key'>"
            f"<input type='hidden' name='id' value='{int(key['id'])}'>"
            f"<button class='btn'>Delete</button></form>"
            f"</td></tr>"
        )
    if not key_rows:
        key_rows = "<tr><td colspan='6'>No API keys yet.</td></tr>"

    model_rows = ""
    for model in models:
        model_rows += (
            f"<tr><td>{esc(model['name'])}</td><td>{'yes' if model['is_default'] else ''}</td>"
            f"<td>{'active' if model['active'] else 'off'}</td><td>"
            f"<form method='post' style='display:inline'><input type='hidden' name='action' value='default_model'>"
            f"<input type='hidden' name='id' value='{int(model['id'])}'>"
            f"<button class='btn green'>Make default</button></form> "
            f"<form method='post' style='display:inline'><input type='hidden' name='action' value='toggle_model'>"
            f"<input type='hidden' name='id' value='{int(model['id'])}'>"
            f"<button class='btn green'>Toggle</button></form> "
            f"<form method='post' style='display:inline'><input type='hidden' name='action' value='del_model'>"
            f"<input type='hidden' name='id' value='{int(model['id'])}'>"
            f"<button class='btn'>Delete</button></form>"
            f"</td></tr>"
        )
    if not model_rows:
        model_rows = "<tr><td colspan='4'>No models yet.</td></tr>"

    provider_options = "".join(
        f"<option value='{esc(name)}'>{esc(name)}</option>" for name in ai_pool.provider_choices())
    last_error = ai_pool.last_error()

    return f"""
    <div class="card"><h3>AI chat</h3>
      <p>Keys are tried in order; a key that fails moves down the list and the next one
      answers. The same pool is used by the bot chat and the Mini App chat.</p>
      {'<p style="color:#c0392b">Last AI error: ' + esc(last_error) + '</p>' if last_error else ''}
      <table><tr><th>Label</th><th>Provider</th><th>Key</th><th>Fails</th><th>State</th><th></th></tr>{key_rows}</table>
      <h4>Add key</h4>
      <form method="post">
        <input type="hidden" name="action" value="add_key">
        <label>Label (optional)</label><input name="label">
        <label>Provider</label><select name="provider">{provider_options}</select>
        <label>API key</label><input name="api_key" autocomplete="off" required>
        <label>Base URL (optional, for OpenAI-compatible providers)</label><input name="base_url">
        <label>Models (comma separated, optional)</label><input name="models" placeholder="gemini-2.5-flash, gemini-flash-lite-latest">
        <button class="btn green">Add key</button>
      </form>
    </div>
    <div class="card"><h3>Models</h3>
      <table><tr><th>Model</th><th>Default</th><th>State</th><th></th></tr>{model_rows}</table>
      <form method="post"><input type="hidden" name="action" value="add_model">
        <input name="name" placeholder="model name"><button class="btn green">Add model</button></form>
    </div>
    <div class="card"><h3>Chat settings</h3>
      <form method="post"><input type="hidden" name="action" value="save_chat">
        <label>System prompt</label>
        <textarea name="system_prompt" rows="6">{esc(ai_pool.chat_system_prompt())}</textarea>
        <label>Temperature (0–2)</label><input name="temperature" value="{esc(ai_pool.setting('temperature', '0.7'))}">
        <label>Max answer tokens</label><input name="max_tokens" value="{esc(ai_pool.setting('max_tokens', '2600'))}">
        <label>History pairs kept in context</label><input name="history_limit" value="{esc(ai_pool.setting('history_limit', '16'))}">
        <label><input type="checkbox" name="markdown" value="1" {'checked' if ai_pool.chat_markdown() else ''}> Convert markdown to Telegram formatting</label>
        <button class="btn green">Save</button>
      </form>
    </div>"""


@app.route("/ai", methods=["GET", "POST"])
def ai_settings():
    if not login_required():
        return redirect("/login")
    import ai_pool
    if request.method == "POST":
        action = request.form.get("action", "")
        try:
            if action == "add_key":
                ai_pool.add_key(request.form.get("label"), request.form.get("api_key"),
                                request.form.get("provider"), request.form.get("base_url"),
                                request.form.get("models"))
            elif action == "toggle_key":
                ai_pool.toggle_key(request.form.get("id") or 0)
            elif action == "del_key":
                ai_pool.delete_key(request.form.get("id") or 0)
            elif action == "add_model":
                ai_pool.add_model(request.form.get("name"))
            elif action == "toggle_model":
                ai_pool.toggle_model(request.form.get("id") or 0)
            elif action == "default_model":
                ai_pool.set_default_model(request.form.get("id") or 0)
            elif action == "del_model":
                ai_pool.delete_model(request.form.get("id") or 0)
            elif action == "save_chat":
                ai_pool.set_setting("system_prompt", request.form.get("system_prompt", ""))
                ai_pool.set_setting("temperature", request.form.get("temperature", "0.7"))
                ai_pool.set_setting("max_tokens", request.form.get("max_tokens", "2600"))
                ai_pool.set_setting("history_limit", request.form.get("history_limit", "16"))
                ai_pool.set_setting("markdown", "1" if request.form.get("markdown") else "0")
        except Exception as exc:
            print(f"[admin] AI sozlamasi: {exc}", flush=True)
        return redirect("/ai")
    return PAGE.replace("{{content|safe}}", _ai_page_content())


def run_web():
    app.run(host=config.WEB_ADMIN_HOST, port=config.WEB_ADMIN_PORT, debug=False)

def start_web_thread():
    t = threading.Thread(target=run_web, daemon=True)
    t.start()
    return t
