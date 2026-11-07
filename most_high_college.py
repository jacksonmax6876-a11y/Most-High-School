"""Most High College: e-admission portal (Flask), one file.

Everything is in this file: the admission form, pages and styling.
Nothing else is needed to run it.

Run:
    pip install flask
    python most_high_college.py    # then open http://localhost:5000

Pages: /apply (admission form, also the home page)   /admin (list of applications)

After a parent submits the form, they tap a button that sends the details to
the admissions office on WhatsApp. Every application is also saved in
admissions.db, created next to this file.

Optional settings: create a file named .env next to this file, for example:
    SECRET_KEY=a-long-random-string
    ADMIN_PASSWORD=choose-a-strong-password    (turns on /admin)
    WHATSAPP_NUMBER=2347068463321              (country code, no +)
Other settings: DB_PATH, PORT.
"""
import hmac
import os
import re
import secrets
import sqlite3
import urllib.parse
from datetime import date, datetime
from pathlib import Path

from jinja2 import DictLoader
from flask import (Flask, Response, abort, g, redirect,
                   render_template, request, session, url_for)

BASE_DIR = Path(__file__).resolve().parent


def load_env():
    """Read KEY=VALUE pairs from .env (or _env) without extra dependencies."""
    for name in (".env", "_env"):
        path = BASE_DIR / name
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("'\""))
            return


load_env()

# ---------------------------------------------------------------- config
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "admissions.db"))
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "2347068463321")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SCHOOL = {
    "name": "Most High College",
    "phone": "08038974154",
    "email": "support@mosthighsch.com.ng",
    "address": "1-3 Oshota Street, Abule Taylor, Lagos",
}

GENDERS = ["Male", "Female"]
CLASSES = ["Nursery"] + [f"Primary {i}" for i in range(1, 7)] + \
          [f"JSS{i}" for i in range(1, 4)] + [f"SS{i}" for i in range(1, 4)]
SOURCES = ["TikTok", "Facebook", "Instagram", "Website", "Referral",
           "Parent Recommendation", "Other"]
TIMES = ["09:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "01:00 PM"]
FIELDS = ["parent_name", "phone", "email", "address", "student_name", "gender",
          "current_school", "desired_class", "source", "appointment_date",
          "appointment_time"]

PHONE_RE = re.compile(r"^(?:\+234|234|0)\d{10}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ------------------------------------------------- embedded assets
CSS = r"""
:root {
  --paper: #f5f7f8;
  --surface: #ffffff;
  --ink: #12222b;
  --muted: #5b6b74;
  --line: #d9e0e4;
  --teal: #0d6b63;
  --teal-dark: #09504a;
  --gold: #e9a820;
  --danger: #b3261e;
  --serif: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.55 var(--sans); min-height: 100vh; display: flex; flex-direction: column; }
main { flex: 1; width: 100%; max-width: 1080px; margin: 0 auto; padding: 32px 20px 48px; }
h1 { font: 600 2rem/1.2 var(--serif); margin: 0 0 12px; }
a { color: var(--teal-dark); }
.muted { color: var(--muted); font-weight: 400; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
:focus-visible { outline: 3px solid var(--gold); outline-offset: 2px; }

.site-header { background: var(--teal); color: #fff; display: flex; flex-wrap: wrap; gap: 8px 28px; align-items: center; justify-content: space-between; padding: 14px 20px; border-bottom: 4px solid var(--gold); }
.brand { font: 600 1.25rem var(--serif); color: #fff; text-decoration: none; }
.tag { color: #e6f3f1; font-size: .85rem; letter-spacing: .06em; text-transform: uppercase; }
.site-header nav { display: flex; gap: 20px; }
.site-header nav a { color: #e6f3f1; text-decoration: none; padding: 4px 0; border-bottom: 2px solid transparent; }
.site-header nav a[aria-current="page"], .site-header nav a:hover { color: #fff; border-bottom-color: var(--gold); }
.site-footer { display: flex; flex-wrap: wrap; gap: 4px 24px; justify-content: center; padding: 18px 20px; color: var(--muted); font-size: .9rem; border-top: 1px solid var(--line); }

button, .btn { font: inherit; cursor: pointer; }
.primary { background: var(--teal); color: #fff; border: 0; border-radius: 6px; padding: 11px 20px; font-weight: 600; text-decoration: none; display: inline-block; text-align: center; }
.primary:hover { background: var(--teal-dark); }
.primary:disabled { opacity: .6; cursor: default; }
.primary.wide { width: 100%; }
.link { background: none; border: 0; color: var(--teal-dark); text-decoration: underline; padding: 0; }


.form-page { max-width: 640px; margin: 0 auto; }
fieldset { border: 1px solid var(--line); background: var(--surface); border-radius: 8px; margin: 0 0 20px; padding: 8px 20px 16px; }
legend { font: 600 1.15rem var(--serif); padding: 0 8px; }
.field { margin-top: 14px; flex: 1; }
.row { display: flex; gap: 16px; flex-wrap: wrap; }
.row .field { min-width: 180px; }
label { display: block; font-weight: 600; margin-bottom: 4px; }
input, select, textarea { width: 100%; font: inherit; color: var(--ink); background: #fff; border: 1px solid #aab7bd; border-radius: 6px; padding: 9px 11px; }
.error { color: var(--danger); margin: 4px 0 0; font-size: .92rem; }
.alert { background: #fbeceb; color: var(--danger); border-left: 4px solid var(--danger); padding: 10px 14px; border-radius: 4px; }
.id-line { font-size: 1.15rem; }
.id-line strong { font: 600 1.3rem var(--serif); background: #fff4d6; padding: 1px 8px; border-radius: 4px; }
.summary { display: grid; grid-template-columns: max-content 1fr; gap: 6px 18px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 16px 20px; }
.summary dt { color: var(--muted); } .summary dd { margin: 0; }
.btn { margin: 8px 0 12px; }

.table-wrap { overflow-x: auto; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line); white-space: nowrap; }

@media (max-width: 800px) {
  h1 { font-size: 1.6rem; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

TEMPLATES = {
    "base.html": r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Most High College{% endblock %}</title>
  <style>{{ CSS|safe }}</style>
</head>
<body>
  <header class="site-header">
    <a class="brand" href="{{ url_for('apply') }}">Most High College</a>
    <span class="tag">E-Admission</span>
  </header>
  <main>{% block content %}{% endblock %}</main>
  <footer class="site-footer">
    <span>{{ school.address }}</span>
    <span>{{ school.phone }}</span>
    <span>{{ school.email }}</span>
  </footer>
  {% block scripts %}{% endblock %}
</body>
</html>
""",
    "apply.html": r"""{% extends "base.html" %}
{% block title %}Apply for admission · Most High College{% endblock %}
{% macro err(name) %}{% if errors.get(name) %}<p class="error" id="{{ name }}-err">{{ errors[name] }}</p>{% endif %}{% endmacro %}
{% macro opts(items, selected) %}{% for i in items %}<option value="{{ i }}"{% if i == selected %} selected{% endif %}>{{ i }}</option>{% endfor %}{% endmacro %}
{% block content %}
<div class="form-page">
  <h1>Apply for admission</h1>
  <p>Complete this form before you visit the school. Appointments are Monday to Friday.</p>
  {% if errors %}<p class="alert" role="alert">Some details need fixing. Check the marked fields and submit again.</p>{% endif %}

  <form method="post" novalidate>
    <fieldset>
      <legend>Parent or guardian</legend>
      <div class="field"><label for="parent_name">Full name</label>
        <input id="parent_name" name="parent_name" value="{{ form.get('parent_name', '') }}" required>{{ err('parent_name') }}</div>
      <div class="field"><label for="phone">Phone number</label>
        <input id="phone" name="phone" type="tel" inputmode="tel" value="{{ form.get('phone', '') }}" required>{{ err('phone') }}</div>
      <div class="field"><label for="email">Email address <span class="muted">(optional)</span></label>
        <input id="email" name="email" type="email" value="{{ form.get('email', '') }}">{{ err('email') }}</div>
      <div class="field"><label for="address">Residential address <span class="muted">(optional)</span></label>
        <textarea id="address" name="address" rows="2">{{ form.get('address', '') }}</textarea></div>
    </fieldset>

    <fieldset>
      <legend>Student</legend>
      <div class="field"><label for="student_name">Full name</label>
        <input id="student_name" name="student_name" value="{{ form.get('student_name', '') }}" required>{{ err('student_name') }}</div>
      <div class="row">
        <div class="field"><label for="gender">Gender</label>
          <select id="gender" name="gender">{{ opts(genders, form.get('gender')) }}</select>{{ err('gender') }}</div>
        <div class="field"><label for="desired_class">Class applying for</label>
          <select id="desired_class" name="desired_class">{{ opts(classes, form.get('desired_class')) }}</select>{{ err('desired_class') }}</div>
      </div>
      <div class="field"><label for="current_school">Current school <span class="muted">(optional)</span></label>
        <input id="current_school" name="current_school" value="{{ form.get('current_school', '') }}"></div>
    </fieldset>

    <fieldset>
      <legend>Visit</legend>
      <div class="row">
        <div class="field"><label for="appointment_date">Appointment date</label>
          <input id="appointment_date" name="appointment_date" type="date" min="{{ today }}" value="{{ form.get('appointment_date', '') }}" required>{{ err('appointment_date') }}</div>
        <div class="field"><label for="appointment_time">Time</label>
          <select id="appointment_time" name="appointment_time">{{ opts(times, form.get('appointment_time')) }}</select>{{ err('appointment_time') }}</div>
      </div>
      <div class="field"><label for="source">How did you hear about us?</label>
        <select id="source" name="source">{{ opts(sources, form.get('source')) }}</select>{{ err('source') }}</div>
    </fieldset>

    <button type="submit" class="primary wide">Submit application</button>
  </form>
</div>
{% endblock %}
""",
    "success.html": r"""{% extends "base.html" %}
{% block title %}Application submitted · Most High College{% endblock %}
{% block content %}
<div class="form-page">
  <h1>Application submitted</h1>
  <p class="id-line">Your application ID is <strong>{{ row['application_id'] }}</strong>. Keep it for your visit.</p>
  <dl class="summary">
    <dt>Student</dt><dd>{{ row['student_name'] }} ({{ row['desired_class'] }})</dd>
    <dt>Parent or guardian</dt><dd>{{ row['parent_name'] }}, {{ row['phone'] }}</dd>
    <dt>Appointment</dt><dd>{{ row['appointment_date'] }} at {{ row['appointment_time'] }}</dd>
  </dl>
  <p>One last step: send these details to the admissions office on WhatsApp.</p>
  <a class="primary wide btn" href="{{ wa_link }}" target="_blank" rel="noopener">Send to admissions office on WhatsApp</a>
  <p class="muted"><a href="{{ url_for('apply') }}">Start another application</a></p>
</div>
{% endblock %}
""",
    "admin.html": r"""{% extends "base.html" %}
{% block title %}Applications · Most High College{% endblock %}
{% block content %}
<div class="admin-page">
  <h1>Applications ({{ rows|length }})</h1>
  <div class="table-wrap">
    <table>
      <thead><tr><th>ID</th><th>Student</th><th>Class</th><th>Parent</th><th>Phone</th><th>Appointment</th><th>Source</th><th>Submitted</th></tr></thead>
      <tbody>
      {% for r in rows %}
        <tr><td>{{ r['application_id'] }}</td><td>{{ r['student_name'] }}</td><td>{{ r['desired_class'] }}</td>
            <td>{{ r['parent_name'] }}</td><td>{{ r['phone'] }}</td>
            <td>{{ r['appointment_date'] }} {{ r['appointment_time'] }}</td><td>{{ r['source'] }}</td><td>{{ r['created_at'] }}</td></tr>
      {% else %}
        <tr><td colspan="8">No applications yet.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
""",
}

app = Flask(__name__, static_folder=None)
app.jinja_loader = DictLoader(TEMPLATES)
app.jinja_env.globals.update(CSS=CSS)
# Set SECRET_KEY in .env so sessions survive restarts.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# -------------------------------------------------------------- database
SCHEMA = """
CREATE TABLE IF NOT EXISTS applications(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT,
    parent_name TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    student_name TEXT,
    gender TEXT,
    dob TEXT,  -- unused; kept so existing admissions.db files stay compatible
    current_school TEXT,
    desired_class TEXT,
    source TEXT,
    appointment_date TEXT,
    appointment_time TEXT,
    created_at TEXT
)
"""


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(SCHEMA)
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_applications_app_id "
                   "ON applications(application_id)")
    except sqlite3.IntegrityError:
        pass  # old data with duplicate IDs; the new code never creates any
    db.commit()
    db.close()


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def save_application(f):
    """Insert and derive the public ID from the row id, so IDs never collide."""
    db = get_db()
    cur = db.execute(
        """INSERT INTO applications(parent_name, phone, email, address,
               student_name, gender, current_school, desired_class, source,
               appointment_date, appointment_time, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (f["parent_name"], f["phone"], f["email"], f["address"],
         f["student_name"], f["gender"], f["current_school"],
         f["desired_class"], f["source"], f["appointment_date"],
         f["appointment_time"], datetime.now().isoformat(sep=" ", timespec="seconds")))
    app_id = f"MH-2027-{cur.lastrowid:04d}"
    db.execute("UPDATE applications SET application_id=? WHERE id=?",
               (app_id, cur.lastrowid))
    db.commit()
    return app_id


def validate(f):
    errors = {}
    if not f["parent_name"]:
        errors["parent_name"] = "Enter the parent or guardian's full name."

    phone = re.sub(r"[\s\-()]", "", f["phone"])
    if not phone:
        errors["phone"] = "Enter a phone number."
    elif not PHONE_RE.match(phone):
        errors["phone"] = "Enter a valid Nigerian number, like 08012345678."
    else:
        f["phone"] = phone

    if f["email"] and not EMAIL_RE.match(f["email"]):
        errors["email"] = "Enter a valid email address, or leave it blank."
    if not f["student_name"]:
        errors["student_name"] = "Enter the student's full name."
    if f["gender"] not in GENDERS:
        errors["gender"] = "Select a gender."
    if f["desired_class"] not in CLASSES:
        errors["desired_class"] = "Select a class."
    if f["source"] not in SOURCES:
        errors["source"] = "Select how you heard about us."
    if f["appointment_time"] not in TIMES:
        errors["appointment_time"] = "Select an appointment time."

    try:
        d = date.fromisoformat(f["appointment_date"])
    except ValueError:
        errors["appointment_date"] = "Choose an appointment date."
    else:
        if d < date.today():
            errors["appointment_date"] = "Choose a date that has not passed."
        elif d.weekday() > 4:
            errors["appointment_date"] = "Appointments are Monday to Friday."
    return errors


def whatsapp_link(row):
    msg = f"""🎓 MOST HIGH COLLEGE
E-ADMISSION REGISTRATION

APPLICATION ID
{row['application_id']}

PARENT INFORMATION
Parent Name: {row['parent_name']}
Phone Number: {row['phone']}
Email: {row['email'] or '-'}
Residential Address: {row['address'] or '-'}

STUDENT INFORMATION
Student Name: {row['student_name']}
Gender: {row['gender']}
Current School: {row['current_school'] or '-'}
Desired Class: {row['desired_class']}

APPOINTMENT DETAILS
Date: {row['appointment_date']}
Time: {row['appointment_time']}

REFERRAL SOURCE
{row['source']}

Submitted via: Most High College E-Admission Portal"""
    return f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(msg)}"


# ---------------------------------------------------------------- pages
@app.route("/")
def home():
    return redirect(url_for("apply"))


@app.route("/apply", methods=["GET", "POST"])
def apply():
    form, errors = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in FIELDS}
        errors = validate(form)
        if not errors:
            session["last_application"] = save_application(form)
            return redirect(url_for("success"))
    return render_template(
        "apply.html", school=SCHOOL, form=form, errors=errors,
        genders=GENDERS, classes=CLASSES, sources=SOURCES, times=TIMES,
        today=date.today().isoformat())


@app.route("/apply/success")
def success():
    app_id = session.get("last_application")
    row = get_db().execute("SELECT * FROM applications WHERE application_id=?",
                           (app_id,)).fetchone() if app_id else None
    if row is None:
        return redirect(url_for("apply"))
    return render_template("success.html", school=SCHOOL, row=row,
                           wa_link=whatsapp_link(row))


@app.route("/admin")
def admin():
    if not ADMIN_PASSWORD:
        abort(404)  # disabled until ADMIN_PASSWORD is set
    auth = request.authorization
    if not (auth and hmac.compare_digest(auth.password or "", ADMIN_PASSWORD)):
        return Response("Login required", 401,
                        {"WWW-Authenticate": 'Basic realm="Admissions"'})
    rows = get_db().execute(
        "SELECT * FROM applications ORDER BY id DESC").fetchall()
    return render_template("admin.html", school=SCHOOL, rows=rows)


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)),
            debug=os.environ.get("FLASK_DEBUG") == "1")
