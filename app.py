import os, re, hmac, hashlib, secrets, sqlite3, time
from functools import wraps
from flask import Flask, g, jsonify, render_template, request, session

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET")
DB_PATH = os.environ.get("DATABASE_PATH", "/tmp/kay_chat.db" if os.environ.get("VERCEL") else "kay_chat.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      display_name TEXT NOT NULL,
      private_hash TEXT NOT NULL UNIQUE,
      public_code TEXT NOT NULL UNIQUE,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS conversations(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      kind TEXT NOT NULL CHECK(kind IN ('direct','group','channel')),
      name TEXT NOT NULL,
      owner_id INTEGER NOT NULL REFERENCES users(id),
      private_hash TEXT,
      public_code TEXT NOT NULL UNIQUE,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS members(
      conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      role TEXT NOT NULL DEFAULT 'member',
      PRIMARY KEY(conversation_id,user_id)
    );
    CREATE TABLE IF NOT EXISTS messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
      sender_id INTEGER NOT NULL REFERENCES users(id),
      body TEXT NOT NULL,
      created_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id,id);
    """)
    conn.commit()
    conn.close()

def code(prefix):
    # Human-readable, high-entropy code; private codes are shown once.
    return prefix + "-" + secrets.token_urlsafe(18).replace("-", "").replace("_", "")[:22].upper()

def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def current_user():
    uid = session.get("uid")
    return db().execute("SELECT id,display_name,public_code FROM users WHERE id=?", (uid,)).fetchone() if uid else None

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return jsonify(error="請先登入"), 401
        return fn(*args, **kwargs)
    return wrapper

def error(message, status=400):
    return jsonify(error=message), status

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "匿名使用者").strip()[:24]
    private_code = code("KAYP")
    public_code = code("KAY")
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO users(display_name,private_hash,public_code,created_at) VALUES(?,?,?,?)",
            (name, digest(private_code), public_code, int(time.time()))
        )
        uid = cur.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        return error("建立帳戶時發生問題，請再試一次", 500)
    session["uid"] = uid
    return jsonify(
        ok=True, name=name, private_code=private_code, public_code=public_code,
        warning="私人 KAY 只會顯示這一次，請自行安全保存。"
    )

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    private_code = (data.get("private_code") or "").strip().upper()
    user = db().execute(
        "SELECT id,display_name,public_code FROM users WHERE private_hash=?",
        (digest(private_code),)
    ).fetchone()
    if not user:
        return error("私人 KAY 編碼不正確", 401)
    session.clear()
    session["uid"] = user["id"]
    return jsonify(ok=True, name=user["display_name"], public_code=user["public_code"])

@app.post("/api/logout")
@login_required
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/me")
@login_required
def me():
    u = current_user()
    return jsonify(name=u["display_name"], public_code=u["public_code"])

@app.post("/api/direct")
@login_required
def start_direct():
    data = request.get_json(silent=True) or {}
    public_code = (data.get("public_code") or "").strip().upper()
    me = current_user()
    target = db().execute("SELECT id,display_name FROM users WHERE public_code=?", (public_code,)).fetchone()
    if not target:
        return error("找不到這個公共 KAY 編碼", 404)
    if target["id"] == me["id"]:
        return error("不能向自己開啟對話")
    conn = db()
    # Reuse the existing 1-to-1 conversation.
    row = conn.execute("""
      SELECT c.id FROM conversations c
      JOIN members a ON a.conversation_id=c.id AND a.user_id=?
      JOIN members b ON b.conversation_id=c.id AND b.user_id=?
      WHERE c.kind='direct' LIMIT 1
    """, (me["id"], target["id"])).fetchone()
    if row:
        return jsonify(ok=True, conversation_id=row["id"])
    cur = conn.execute(
        "INSERT INTO conversations(kind,name,owner_id,public_code,created_at) VALUES('direct',?,?,?,?)",
        (target["display_name"], me["id"], code("DM"), int(time.time()))
    )
    cid = cur.lastrowid
    conn.executemany("INSERT INTO members(conversation_id,user_id,role) VALUES(?,?,?)",
                     [(cid, me["id"], "owner"), (cid, target["id"], "member")])
    conn.commit()
    return jsonify(ok=True, conversation_id=cid)

@app.post("/api/conversations")
@login_required
def create_conversation():
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    name = (data.get("name") or "").strip()[:40]
    if kind not in ("group", "channel") or not name:
        return error("請輸入名稱並選擇群組或頻道")
    me = current_user()
    private_code = code("KAYP")
    public_code = code("KAY")
    conn = db()
    cur = conn.execute("""
      INSERT INTO conversations(kind,name,owner_id,private_hash,public_code,created_at)
      VALUES(?,?,?,?,?,?)
    """, (kind, name, me["id"], digest(private_code), public_code, int(time.time())))
    cid = cur.lastrowid
    conn.execute("INSERT INTO members(conversation_id,user_id,role) VALUES(?,?,?)", (cid, me["id"], "owner"))
    conn.commit()
    return jsonify(ok=True, id=cid, name=name, kind=kind,
                   private_code=private_code, public_code=public_code,
                   warning="管理用私人 KAY 只會顯示這一次，請自行保存。")

@app.post("/api/join")
@login_required
def join_conversation():
    data = request.get_json(silent=True) or {}
    public_code = (data.get("public_code") or "").strip().upper()
    me = current_user()
    conv = db().execute("SELECT id,kind FROM conversations WHERE public_code=?", (public_code,)).fetchone()
    if not conv or conv["kind"] == "direct":
        return error("找不到可加入的群組或頻道", 404)
    db().execute("INSERT OR IGNORE INTO members(conversation_id,user_id,role) VALUES(?,?,?)",
                 (conv["id"], me["id"], "member"))
    db().commit()
    return jsonify(ok=True, id=conv["id"])

@app.get("/api/conversations")
@login_required
def conversations():
    me = current_user()
    rows = db().execute("""
      SELECT c.id,c.kind,c.name,c.public_code,
        (SELECT body FROM messages WHERE conversation_id=c.id ORDER BY id DESC LIMIT 1) AS last_message
      FROM conversations c JOIN members m ON m.conversation_id=c.id
      WHERE m.user_id=? ORDER BY c.id DESC
    """, (me["id"],)).fetchall()
    return jsonify(items=[dict(r) for r in rows])

def is_member(cid, uid):
    return db().execute("SELECT 1 FROM members WHERE conversation_id=? AND user_id=?", (cid,uid)).fetchone() is not None

@app.get("/api/messages/<int:cid>")
@login_required
def get_messages(cid):
    me = current_user()
    if not is_member(cid, me["id"]):
        return error("你沒有這個對話的存取權", 403)
    rows = db().execute("""
      SELECT messages.id,messages.body,messages.created_at,users.display_name
      FROM messages JOIN users ON users.id=messages.sender_id
      WHERE conversation_id=? ORDER BY messages.id DESC LIMIT 100
    """, (cid,)).fetchall()
    return jsonify(items=[dict(r) for r in reversed(rows)])

@app.post("/api/messages/<int:cid>")
@login_required
def send_message(cid):
    me = current_user()
    if not is_member(cid, me["id"]):
        return error("你沒有這個對話的存取權", 403)
    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body or len(body) > 2000:
        return error("訊息不可為空，且最多 2000 字")
    db().execute("INSERT INTO messages(conversation_id,sender_id,body,created_at) VALUES(?,?,?,?)",
                 (cid, me["id"], body, int(time.time())))
    db().commit()
    return jsonify(ok=True)

init_db()  # 建立原型資料表；Vercel 的 /tmp 僅供示範，並非永久儲存。\n\nif __name__ == "__main__":
    app.run(host="127.0.0.1", port=9008, debug=True)
