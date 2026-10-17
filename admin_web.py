"""Web admin panel — Flask based. Starts with the bot. English UI."""
import sqlite3
import threading
from flask import Flask, request, session, redirect, render_template_string, url_for
import config

app = Flask(__name__)
app.secret_key = config.AI_API_KEY

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
<div class="nav"><a href="/">Dashboard</a><a href="/users">Users</a><a href="/orders">Orders</a><a href="/checks">Receipts</a><a href="/settings">Settings</a><a href="/logout">Logout</a></div>
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
        if request.form.get("password") == config.WEB_ADMIN_PASSWORD:
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
    {''.join(f"<tr><td>{o['id']}</td><td>{o['user_id']}</td><td>{o['service']}</td><td>{o['topic'][:40]}</td><td>{o['price']}</td><td>{o['created_at']}</td></tr>" for o in q("SELECT * FROM orders ORDER BY id DESC LIMIT 10"))}
    </table></div>"""
    return PAGE.replace("{{content|safe}}", content)

@app.route("/users")
def users():
    if not login_required(): return redirect("/login")
    rows = q("SELECT * FROM users ORDER BY created_at DESC LIMIT 200")
    content = '<div class="card"><h3>Users (last 200)</h3><table><tr><th>ID</th><th>Username</th><th>Name</th><th>Lang</th><th>Balance</th><th>Bonus</th><th>Referred by</th></tr>'
    for u in rows:
        content += f"<tr><td>{u['telegram_id']}</td><td>@{u['username'] or '-'}</td><td>{u['first_name'] or '-'}</td><td>{u['lang']}</td><td>{u['balance']}</td><td>{u['bonus_balance']}</td><td>{u['referred_by'] or '-'}</td></tr>"
    content += "</table></div>"
    return PAGE.replace("{{content|safe}}", content)

@app.route("/orders")
def orders():
    if not login_required(): return redirect("/login")
    rows = q("SELECT * FROM orders ORDER BY id DESC LIMIT 200")
    content = '<div class="card"><h3>Orders</h3><table><tr><th>ID</th><th>User</th><th>Service</th><th>Topic</th><th>Price</th><th>Status</th></tr>'
    for o in rows:
        content += f"<tr><td>{o['id']}</td><td>{o['user_id']}</td><td>{o['service']}</td><td>{o['topic'][:50]}</td><td>{o['price']}</td><td>{o['status']}</td></tr>"
    content += "</table></div>"
    return PAGE.replace("{{content|safe}}", content)

@app.route("/checks")
def checks():
    if not login_required(): return redirect("/login")
    rows = q("SELECT * FROM checks ORDER BY id DESC LIMIT 100")
    content = '<div class="card"><h3>Payment Receipts</h3><table><tr><th>ID</th><th>User</th><th>Amount</th><th>Status</th><th>Action</th></tr>'
    for c in rows:
        badge = f'<span class="badge b-{c["status"]}">{c["status"]}</span>'
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
    content = f"""<div class="card"><h3>Settings</h3><form method="post">
    <label>Referral percent:</label><input name="referral_percent" value="{ref[0]['value'] if ref else '10'}">
    <label>Payment info:</label><textarea name="payment_info" rows="4">{pay[0]['value'] if pay else ''}</textarea>
    <label>Mode (1=free, 0=paid):</label><input name="free_mode" value="{free[0]['value'] if free else '1'}">
    <button class="btn green">Save</button></form></div>"""
    return PAGE.replace("{{content|safe}}", content)

def run_web():
    app.run(host=config.WEB_ADMIN_HOST, port=config.WEB_ADMIN_PORT, debug=False)

def start_web_thread():
    t = threading.Thread(target=run_web, daemon=True)
    t.start()
    return t
