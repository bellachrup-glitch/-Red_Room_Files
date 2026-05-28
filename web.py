from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import datetime, timedelta
import json
import os
from threading import Lock

app = Flask(__name__)
app.secret_key = "secret123"

# ================= ADMIN LOGIN =================
ADMIN_EMAIL = "Killermesh273@gmail.com"
ADMIN_PASSWORD = "0547761840killer"

USERS_FILE = "users.json"
POSTS_FILE = "posts.json"
UPLOAD_FOLDER = "static/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ✅ منع تضارب الكتابة
file_lock = Lock()

# ================= HELPERS =================

def safe_read(path):
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except:
        return {}


def safe_write(path, data):
    with file_lock:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)


def load():

    if not os.path.exists(USERS_FILE):
        return {}

    try:
        with open(USERS_FILE, "r") as f:
            content = f.read().strip()

            if not content:
                return {}

            return json.loads(content)

    except:
        return {}


def save(data):
    safe_write(USERS_FILE, data)


def load_posts():

    data = safe_read(POSTS_FILE)

    for p in data:
        data[p].setdefault("likes", 0)
        data[p].setdefault("comments", [])
        data[p].setdefault("liked_by", [])   # ✅ الحل هنا

    return data


def save_posts(data):
    safe_write(POSTS_FILE, data)


def get_ip():
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr


def get_live_users():
    return load()


# ================= HOME =================

@app.route("/")
def home():

    users = load()

    if "user" in session:
        uid = session["user"]
        if uid in users:
            users[uid]["last_seen"] = datetime.now().isoformat()
            save(users)

    return render_template("login.html")

def cleanup_users():

    users = load()
    now = datetime.now()
    cleaned = {}

    for uid, u in users.items():

        last_seen = u.get("last_seen")

        if not last_seen:
            continue

        try:
            last_seen_time = datetime.fromisoformat(last_seen)

            # حذف فقط بعد 24 ساعة
            if now - last_seen_time < timedelta(hours=24):
                cleaned[uid] = u

        except:
            cleaned[uid] = u

    save(cleaned)
# ================= LOGIN =================

@app.route("/login", methods=["POST"])
def login():

    name = request.form.get("name")
    gender = request.form.get("gender")
    age = request.form.get("age")
    national_id = request.form.get("national_id")

    if not name or not national_id:
        return "Missing data"

    users = load()
    ip = get_ip()
    uid = national_id

    users.setdefault(uid, {
        "visits": 0
    })

    users[uid].update({
        "name": name,
        "gender": gender,
        "age": age,
        "id": national_id,
        "ip": ip,
        "last_seen": datetime.now().isoformat(),
        "online": True
    })

    users[uid]["visits"] += 1

    save(users)

    session.clear()
    session["user"] = uid

    return redirect("/feed")


# ================= FEED =================

@app.route("/feed")
def feed():

    if "user" not in session:
        return redirect("/")

    users = load()
    posts = load_posts()

    user = users.get(session["user"])

    return render_template("guest.html", user=user, posts=posts)


@app.route("/welcome")
def welcome():
    return redirect("/feed")


# ================= HEARTBEAT =================

@app.route("/heartbeat")
def heartbeat():

    if "user" in session:

        users = load()
        uid = session["user"]

        if uid in users:
            users[uid]["last_seen"] = datetime.now().isoformat()
            users[uid]["online"] = True
            save(users)

    return "OK"


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    users = load()

    if "user" in session:
        uid = session["user"]
        if uid in users:
            users[uid]["online"] = False

    session.clear()
    save(users)

    return redirect("/")


@app.route("/admin-logout")
def admin_logout():
    session.clear()
    return redirect("/")


# ================= LIKE (ANTI SPAM) =================

@app.route("/like/<image>", methods=["POST"])
def like(image):

    if "user" not in session:
        return jsonify({"likes": 0})

    posts = load_posts()

    if image not in posts:
        return jsonify({"likes": 0})

    user = session["user"]

    # تأكد وجود القائمة
    posts[image].setdefault("liked_by", [])

    # منع سبام اللايك
    if user not in posts[image]["liked_by"]:
        posts[image]["liked_by"].append(user)
        posts[image]["likes"] += 1

        save_posts(posts)

    return jsonify({
        "likes": posts[image]["likes"]
    })


# ================= COMMENT =================

@app.route("/comment/<image>", methods=["POST"])
def comment(image):

    if "user" not in session:
        return redirect("/")

    text = request.form.get("comment")

    posts = load_posts()
    users = load()

    username = users.get(session["user"], {}).get("name", "Guest")

    if image in posts and text:

        posts[image]["comments"].append({
            "user": username,
            "text": text,
            "time": datetime.now().strftime("%d %b %Y - %H:%M")
        })

    save_posts(posts)

    return redirect("/feed")


# ================= ADMIN =================

@app.route("/admin", methods=["GET", "POST"])
def admin():

    cleanup_users()

    users = load()
    posts = load_posts()

    if not session.get("admin"):

        if request.method == "POST":
            if request.form.get("email") == ADMIN_EMAIL and \
               request.form.get("password") == ADMIN_PASSWORD:

                session.clear()
                session["admin"] = True
                return redirect("/admin")

        return render_template("login.html")

    if request.method == "POST":

        file = request.files.get("image")
        caption = request.form.get("caption")

        if file and file.filename:

            filepath = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filepath)

            posts = {
                file.filename: {
                    "caption": caption,
                    "time": str(datetime.now()),
                    "likes": 0,
                    "comments": []
                },
                **posts
            }

            save_posts(posts)
            return redirect("/admin")

    online_users = {}
    now = datetime.now()

    for uid, u in users.items():

        try:
            last = datetime.fromisoformat(u.get("last_seen"))
            u["online"] = (now - last) < timedelta(seconds=15)
        except:
            u["online"] = False

        if u["online"]:
            online_users[uid] = u

    save(users)

    return render_template(
        "admin.html",
        users=users,
        posts=posts,
        online_users=online_users
    )


# ================= DELETE =================

@app.route("/delete/<image>")
def delete_post(image):

    if "admin" not in session:
        return redirect("/")

    posts = load_posts()

    if image in posts:

        path = os.path.join(UPLOAD_FOLDER, image)
        if os.path.exists(path):
            os.remove(path)

        del posts[image]
        save_posts(posts)

    return redirect("/admin")


@app.route("/delete-comment/<image>/<int:index>")
def delete_comment(image, index):

    if "admin" not in session:
        return redirect("/")

    posts = load_posts()

    if image in posts:
        comments = posts[image]["comments"]

        if 0 <= index < len(comments):
            comments.pop(index)

        save_posts(posts)

    return redirect("/admin")


# ================= APIs =================

@app.route("/posts")
def posts_api():
    return jsonify(load_posts())


@app.route("/live-users")
def live_users_api():

    if "admin" not in session:
        return jsonify({})

    users = load()
    now = datetime.now()

    for uid, u in users.items():
        try:
            last = datetime.fromisoformat(u.get("last_seen"))
            u["online"] = (now - last) < timedelta(seconds=15)
        except:
            u["online"] = False

    save(users)
    return jsonify(users)


@app.route("/map-data")
def map_data():

    if not session.get("admin"):
        return jsonify([])

    users = load()
    now = datetime.now()
    result = []

    for u in users.values():

        ip = u.get("ip")
        last_seen = u.get("last_seen")

        if not ip or not last_seen:
            continue

        if ip.startswith(("127.", "192.168.", "10.", "172.")):
            continue

        try:
            last = datetime.fromisoformat(last_seen)
            if now - last < timedelta(seconds=60):
                result.append({
                    "name": u.get("name"),
                    "ip": ip
                })
        except:
            pass

    return jsonify(result)


# ================= RUN =================

if __name__ == "__main__":
    app.run()
