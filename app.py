import os
import secrets
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

DB_NAME = "gold_standard.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_NAME)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT NOT NULL DEFAULT 'business',
            business_name TEXT,
            town TEXT,
            category TEXT,
            invite_code TEXT UNIQUE,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            customer_email TEXT NOT NULL,
            town TEXT NOT NULL,
            category TEXT NOT NULL,
            assigned_to INTEGER,
            status TEXT DEFAULT 'new',
            sent_by INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT,
            contact_name TEXT,
            email TEXT,
            phone TEXT,
            town TEXT,
            category TEXT,
            notes TEXT,
            created_at TEXT
        );
    """)
    admin = db.execute("SELECT id FROM users WHERE role = 'admin'").fetchone()
    if not admin:
        db.execute(
            "INSERT INTO users (username, password_hash, role, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
            ("admin", generate_password_hash("changeme123"), "admin", datetime.utcnow().isoformat())
        )
        db.commit()
        print("Default admin created → username: admin | password: changeme123")

BASE_STYLE = """
<style>
    body { font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f8f9fa; color: #222; }
    h1, h2 { color: #1a1a1a; }
    .card { background: white; border-radius: 12px; padding: 28px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 24px; }
    input, select, textarea { width: 100%; padding: 12px; margin: 8px 0 16px; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; font-size: 16px; }
    button, .btn { display: inline-block; padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; text-decoration: none; }
    button:hover { background: #0056b3; }
    .btn-green { background: #28a745; }
    .btn-red { background: #dc3545; }
    table { width: 100%; border-collapse: collapse; margin-top: 16px; }
    th, td { padding: 12px; border-bottom: 1px solid #eee; text-align: left; }
    th { background: #f1f3f5; }
    .stats { display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }
    .stat { flex: 1; min-width: 140px; background: #e9f2ff; padding: 20px; border-radius: 10px; text-align: center; }
    .stat strong { font-size: 28px; display: block; }
    .flash { padding: 12px; background: #d4edda; border-radius: 8px; margin-bottom: 16px; }
    .logo { max-height: 60px; margin-bottom: 12px; }
</style>
"""

HTML_PUBLIC = """
<!DOCTYPE html>
<html>
<head><title>Gold Standard Marketing</title>""" + BASE_STYLE + """</head>
<body>
    <div class="card">
        <img class="logo" src="https://via.placeholder.com/200x60?text=Gold+Standard" alt="Gold Standard Marketing">
        <h1>Gold Standard Marketing</h1>
        <p>Connect with the top-rated local professional in your area.</p>
        <form method="post" action="/submit-lead">
            <input type="text" name="name" placeholder="Your full name" required>
            <input type="tel" name="phone" placeholder="Phone number" required>
            <input type="email" name="email" placeholder="Email address" required>
            <select name="town" required>
                <option value="">Select your town</option>
                <option value="Rochester">Rochester</option>
                <option value="Henrietta">Henrietta</option>
                <option value="Pittsford">Pittsford</option>
                <option value="Brighton">Brighton</option>
                <option value="Greece">Greece</option>
            </select>
            <select name="category" required>
                <option value="">Select service needed</option>
                <option value="Plumbing">Plumbing</option>
                <option value="Electrical">Electrical</option>
                <option value="HVAC">HVAC</option>
                <option value="Roofing">Roofing</option>
                <option value="Landscaping">Landscaping</option>
                <option value="Painting">Painting</option>
            </select>
            <button type="submit">Get Connected</button>
        </form>
        <p style="margin-top:24px;font-size:14px;color:#666;">
            Are you a business owner interested in joining the network? <a href="/inquiry">Apply here</a>
        </p>
    </div>
</body>
</html>
"""

HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head><title>Login</title>""" + BASE_STYLE + """</head>
<body>
    <div class="card" style="max-width:400px;margin:60px auto;">
        <h2>Login</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form method="post">
            <input type="text" name="username" placeholder="Username" required>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit">Log in</button>
        </form>
        <p style="margin-top:16px;"><a href="/signup">Have an invite code? Sign up</a></p>
        <p><a href="/">← Back</a></p>
    </div>
</body>
</html>
"""

HTML_SIGNUP = """
<!DOCTYPE html>
<html>
<head><title>Sign up</title>""" + BASE_STYLE + """</head>
<body>
    <div class="card" style="max-width:400px;margin:60px auto;">
        <h2>Business Owner Signup</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form method="post">
            <input type="text" name="username" placeholder="Choose a username" required>
            <input type="password" name="password" placeholder="Choose a password" required>
            <input type="text" name="invite_code" placeholder="Invite code" required>
            <button type="submit" class="btn-green">Create account</button>
        </form>
        <p style="margin-top:16px;"><a href="/login">Already have an account?</a></p>
    </div>
</body>
</html>
"""

HTML_INQUIRY = """
<!DOCTYPE html>
<html>
<head><title>Join the Network</title>""" + BASE_STYLE + """</head>
<body>
    <div class="card">
        <h1>Interested in joining Gold Standard?</h1>
        <p>Fill out the form below. We’ll check availability in your area and category.</p>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form method="post" action="/submit-inquiry">
            <input type="text" name="business_name" placeholder="Business name" required>
            <input type="text" name="contact_name" placeholder="Your name" required>
            <input type="email" name="email" placeholder="Email" required>
            <input type="tel" name="phone" placeholder="Phone" required>
            <input type="text" name="town" placeholder="Town / area you serve" required>
            <input type="text" name="category" placeholder="Service category" required>
            <textarea name="notes" rows="3" placeholder="Anything else we should know?"></textarea>
            <button type="submit" class="btn-green">Submit inquiry</button>
        </form>
        <p style="margin-top:20px;"><a href="/">← Back</a></p>
    </div>
</body>
</html>
"""

HTML_BUSINESS = """
<!DOCTYPE html>
<html>
<head><title>Dashboard</title>""" + BASE_STYLE + """</head>
<body>
    <p><strong>{{ username }}</strong> | <a href="/logout">Logout</a></p>
    <h1>Your Dashboard</h1>
    <div class="stats">
        <div class="stat"><strong>{{ sent_count }}</strong> Leads you sent</div>
        <div class="stat"><strong>{{ received_count }}</strong> Leads you received</div>
    </div>
    <div class="card">
        <h2>Network Lead Counts</h2>
        <table>
            <tr><th>Business</th><th>Town</th><th>Category</th><th>Sent</th><th>Received</th></tr>
            {% for row in network_counts %}
            <tr>
                <td>{{ row.business_name or row.username }}</td>
                <td>{{ row.town or '—' }}</td>
                <td>{{ row.category or '—' }}</td>
                <td>{{ row.sent }}</td>
                <td>{{ row.received }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <div class="card">
        <h2>Leads assigned to you</h2>
        {% if my_leads %}
        <table>
            <tr><th>Customer</th><th>Phone</th><th>Email</th><th>Town</th><th>Category</th><th>Status</th><th>Update</th></tr>
            {% for lead in my_leads %}
            <tr>
                <td>{{ lead.customer_name }}</td>
                <td>{{ lead.customer_phone }}</td>
                <td>{{ lead.customer_email }}</td>
                <td>{{ lead.town }}</td>
                <td>{{ lead.category }}</td>
                <td>{{ lead.status }}</td>
                <td>
                    <form method="post" action="/update-status" style="margin:0;">
                        <input type="hidden" name="lead_id" value="{{ lead.id }}">
                        <select name="status" onchange="this.form.submit()">
                            <option value="new" {% if lead.status=='new' %}selected{% endif %}>New</option>
                            <option value="contacted" {% if lead.status=='contacted' %}selected{% endif %}>Contacted</option>
                            <option value="in_progress" {% if lead.status=='in_progress' %}selected{% endif %}>In Progress</option>
                            <option value="completed" {% if lead.status=='completed' %}selected{% endif %}>Completed</option>
                            <option value="lost" {% if lead.status=='lost' %}selected{% endif %}>Lost</option>
                        </select>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>No leads assigned to you yet.</p>
        {% endif %}
    </div>
</body>
</html>
"""

HTML_ADMIN = """
<!DOCTYPE html>
<html>
<head><title>Admin</title>""" + BASE_STYLE + """</head>
<body>
    <p><strong>Admin</strong> | <a href="/admin/create-invite">Create Invite</a> | <a href="/logout">Logout</a></p>
    <h1>Admin Dashboard</h1>
    <div class="card">
        <h2>All Leads</h2>
        <table>
            <tr><th>ID</th><th>Customer</th><th>Phone</th><th>Email</th><th>Town</th><th>Category</th><th>Status</th><th>Assigned</th><th>Created</th></tr>
            {% for lead in all_leads %}
            <tr>
                <td>{{ lead.id }}</td>
                <td>{{ lead.customer_name }}</td>
                <td>{{ lead.customer_phone }}</td>
                <td>{{ lead.customer_email }}</td>
                <td>{{ lead.town }}</td>
                <td>{{ lead.category }}</td>
                <td>{{ lead.status }}</td>
                <td>{{ lead.assigned_name or '—' }}</td>
                <td>{{ lead.created_at[:16] }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <div class="card">
        <h2>Business Owners</h2>
        <table>
            <tr><th>Username</th><th>Business</th><th>Town</th><th>Category</th><th>Active</th><th>Action</th></tr>
            {% for u in business_users %}
            <tr>
                <td>{{ u.username }}</td>
                <td>{{ u.business_name or '—' }}</td>
                <td>{{ u.town or '—' }}</td>
                <td>{{ u.category or '—' }}</td>
                <td>{{ 'Yes' if u.is_active else 'No' }}</td>
                <td>
                    <form method="post" action="/admin/toggle-user" style="margin:0;">
                        <input type="hidden" name="user_id" value="{{ u.id }}">
                        <button type="submit" class="{% if u.is_active %}btn-red{% else %}btn-green{% endif %}">
                            {{ 'Deactivate' if u.is_active else 'Activate' }}
                        </button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <div class="card">
        <h2>Join Inquiries</h2>
        {% if inquiries %}
        <table>
            <tr><th>Business</th><th>Contact</th><th>Email</th><th>Phone</th><th>Town</th><th>Category</th><th>Notes</th><th>Date</th></tr>
            {% for i in inquiries %}
            <tr>
                <td>{{ i.business_name }}</td>
                <td>{{ i.contact_name }}</td>
                <td>{{ i.email }}</td>
                <td>{{ i.phone }}</td>
                <td>{{ i.town }}</td>
                <td>{{ i.category }}</td>
                <td>{{ i.notes or '—' }}</td>
                <td>{{ i.created_at[:16] }}</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p>No inquiries yet.</p>
        {% endif %}
    </div>
</body>
</html>
"""

HTML_CREATE_INVITE = """
<!DOCTYPE html>
<html>
<head><title>Create Invite</title>""" + BASE_STYLE + """</head>
<body>
    <div class="card" style="max-width:500px;">
        <h2>Create Invite Code</h2>
        {% with messages = get_flashed_messages() %}
          {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        <form method="post">
            <input type="text" name="business_name" placeholder="Business name" required>
            <input type="text" name="town" placeholder="Town" required>
            <input type="text" name="category" placeholder="Category" required>
            <button type="submit" class="btn-green">Generate Invite Code</button>
        </form>
        <p style="margin-top:20px;"><a href="/admin">← Back to admin</a></p>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PUBLIC)

@app.route("/submit-lead", methods=["POST"])
def submit_lead():
    name = request.form["name"].strip()
    phone = request.form["phone"].strip()
    email = request.form["email"].strip()
    town = request.form["town"]
    category = request.form["category"]
    db = get_db()
    owner = db.execute(
        "SELECT id, username FROM users WHERE role='business' AND is_active=1 AND town=? AND category=? LIMIT 1",
        (town, category)
    ).fetchone()
    assigned_to = owner["id"] if owner else None
    db.execute(
        "INSERT INTO leads (customer_name, customer_phone, customer_email, town, category, assigned_to, status, created_at) VALUES (?, ?, ?, ?, ?, ?, 'new', ?)",
        (name, phone, email, town, category, assigned_to, datetime.utcnow().isoformat())
    )
    db.commit()
    print(f"[NOTIFY] New lead → {category} in {town}")
    return """<!DOCTYPE html><html><body style="font-family:system-ui;text-align:center;padding:60px;">
    <h1>Thank you!</h1>
    <p>Your request has been received. The local professional will contact you shortly.</p>
    <a href="/">Back to home</a></body></html>"""

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and user["is_active"] and user["password_hash"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("business_dashboard"))
        flash("Invalid username or password, or account is inactive.")
    return render_template_string(HTML_LOGIN)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        invite_code = request.form["invite_code"].strip()
        db = get_db()
        invite = db.execute(
            "SELECT * FROM users WHERE invite_code = ? AND role = 'business' AND username IS NULL",
            (invite_code,)
        ).fetchone()
        if not invite:
            flash("Invalid or already-used invite code.")
            return render_template_string(HTML_SIGNUP)
        try:
            db.execute(
                "UPDATE users SET username = ?, password_hash = ?, is_active = 1 WHERE id = ?",
                (username, generate_password_hash(password), invite["id"])
            )
            db.commit()
            flash("Account created! You can now log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That username is already taken.")
    return render_template_string(HTML_SIGNUP)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
def business_dashboard():
    if session.get("role") != "business":
        return redirect(url_for("login"))
    db = get_db()
    user_id = session["user_id"]
    my_leads = db.execute("SELECT * FROM leads WHERE assigned_to = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    sent_count = db.execute("SELECT COUNT(*) FROM leads WHERE sent_by = ?", (user_id,)).fetchone()[0]
    received_count = db.execute("SELECT COUNT(*) FROM leads WHERE assigned_to = ?", (user_id,)).fetchone()[0]
    network_counts = db.execute("""
        SELECT u.username, u.business_name, u.town, u.category,
               (SELECT COUNT(*) FROM leads WHERE sent_by = u.id) as sent,
               (SELECT COUNT(*) FROM leads WHERE assigned_to = u.id) as received
        FROM users u
        WHERE u.role = 'business' AND u.is_active = 1 AND u.username IS NOT NULL
        ORDER BY u.town, u.category
    """).fetchall()
    return render_template_string(HTML_BUSINESS, username=session["username"], my_leads=my_leads,
                                  sent_count=sent_count, received_count=received_count, network_counts=network_counts)

@app.route("/update-status", methods=["POST"])
def update_status():
    if session.get("role") != "business":
        return redirect(url_for("login"))
    lead_id = request.form["lead_id"]
    status = request.form["status"]
    db = get_db()
    db.execute("UPDATE leads SET status = ? WHERE id = ? AND assigned_to = ?", (status, lead_id, session["user_id"]))
    db.commit()
    return redirect(url_for("business_dashboard"))

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    db = get_db()
    all_leads = db.execute("""
        SELECT l.*, u.username as assigned_name
        FROM leads l LEFT JOIN users u ON l.assigned_to = u.id
        ORDER BY l.created_at DESC
    """).fetchall()
    business_users = db.execute("SELECT * FROM users WHERE role = 'business' ORDER BY town, category").fetchall()
    inquiries = db.execute("SELECT * FROM inquiries ORDER BY created_at DESC").fetchall()
    return render_template_string(HTML_ADMIN, all_leads=all_leads, business_users=business_users, inquiries=inquiries)

@app.route("/admin/create-invite", methods=["GET", "POST"])
def create_invite():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        business_name = request.form["business_name"].strip()
        town = request.form["town"].strip()
        category = request.form["category"].strip()
        code = secrets.token_urlsafe(8).upper()
        db = get_db()
        db.execute(
            "INSERT INTO users (role, business_name, town, category, invite_code, is_active, created_at) VALUES ('business', ?, ?, ?, ?, 0, ?)",
            (business_name, town, category, code, datetime.utcnow().isoformat())
        )
        db.commit()
        flash(f"Invite code created: {code}")
        return redirect(url_for("create_invite"))
    return render_template_string(HTML_CREATE_INVITE)

@app.route("/admin/toggle-user", methods=["POST"])
def toggle_user():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    user_id = request.form["user_id"]
    db = get_db()
    user = db.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        new_status = 0 if user["is_active"] else 1
        db.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        db.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/inquiry")
def inquiry():
    return render_template_string(HTML_INQUIRY)

@app.route("/submit-inquiry", methods=["POST"])
def submit_inquiry():
    db = get_db()
    db.execute(
        "INSERT INTO inquiries (business_name, contact_name, email, phone, town, category, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (request.form["business_name"].strip(), request.form["contact_name"].strip(),
         request.form["email"].strip(), request.form["phone"].strip(),
         request.form["town"].strip(), request.form["category"].strip(),
         request.form.get("notes", "").strip(), datetime.utcnow().isoformat())
    )
    db.commit()
    flash("Thank you! We’ll review your inquiry and get back to you soon.")
    return redirect(url_for("inquiry"))

if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)