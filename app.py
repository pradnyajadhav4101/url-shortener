from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import random
import string
import qrcode
import os

app = Flask(__name__)
app.secret_key = "secret123"


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            original TEXT NOT NULL,
            short TEXT UNIQUE NOT NULL,
            clicks INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


init_db()


# ---------------- HELPERS ----------------
def generate_short_code(length=6):
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def ensure_static_folder():
    if not os.path.exists("static"):
        os.makedirs("static")


# ---------------- AUTH ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if not username or not password:
            message = "Please fill all fields."
            return render_template("register.html", message=message)

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except sqlite3.IntegrityError:
            conn.close()
            message = "Username already exists."

    return render_template("register.html", message=message)


@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        user = cur.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()

        conn.close()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/")

        message = "Invalid username or password."

    return render_template("login.html", message=message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- HOME ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect("/login")

    message = ""

    if request.method == "POST":
        original = request.form["url"].strip()
        custom = request.form.get("custom", "").strip()

        if not original:
            message = "Please enter a valid URL."
            return render_template("index.html", message=message)

        short = custom if custom else generate_short_code()

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO urls (user_id, original, short) VALUES (?, ?, ?)",
                (session["user_id"], original, short)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            message = "Short code already exists. Try another one."
            return render_template("index.html", message=message)

        conn.close()

        ensure_static_folder()

        qr_url = request.host_url.rstrip("/") + "/" + short
        img = qrcode.make(qr_url)
        img.save(f"static/{short}.png")

        return render_template("result.html", short=short, qr_url=qr_url)

    return render_template("index.html", message=message)


# ---------------- REDIRECT ----------------
@app.route("/<short>")
def redirect_url(short):
    # avoid conflict with known routes
    if short in ["login", "register", "logout", "dashboard", "delete", "static"]:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    row = cur.execute(
        "SELECT original FROM urls WHERE short=?",
        (short,)
    ).fetchone()

    if row:
        cur.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short=?",
            (short,)
        )
        conn.commit()
        conn.close()
        return redirect(row[0])

    conn.close()
    return "URL Not Found"


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    data = cur.execute(
        "SELECT original, short, clicks FROM urls WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template("dashboard.html", data=data)


# ---------------- DELETE ----------------
@app.route("/delete/<short>")
def delete(short):
    if "user_id" not in session:
        return redirect("/login")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM urls WHERE short=? AND user_id=?",
        (short, session["user_id"])
    )
    conn.commit()
    conn.close()

    qr_path = os.path.join("static", f"{short}.png")
    if os.path.exists(qr_path):
        os.remove(qr_path)

    return redirect("/dashboard")


# ---------------- RUN ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)