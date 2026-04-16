"""
Database — SQLite via raw sqlite3
Tables: users, conversations, messages
"""

import sqlite3
import os

if os.getenv("VERCEL"):
    DB_PATH = "/tmp/neu_chatbot.db"
else:
    DB_PATH = "data/neu_chatbot.db"
    os.makedirs("data", exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            avatar       TEXT,
            provider     TEXT NOT NULL,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id           TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title        TEXT NOT NULL DEFAULT 'New conversation',
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content         TEXT NOT NULL,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_msg_conv  ON messages(conversation_id, id ASC);

        CREATE TABLE IF NOT EXISTS canvas_config (
            user_id      TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            canvas_url   TEXT NOT NULL,
            canvas_token TEXT NOT NULL,
            updated_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS whatsapp_config (
            user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            phone      TEXT NOT NULL,
            enabled    INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            item_id       TEXT NOT NULL,
            item_type     TEXT NOT NULL,
            title         TEXT NOT NULL,
            course        TEXT,
            due_at        TEXT,
            urgency       TEXT DEFAULT 'low',
            whatsapp_sent INTEGER DEFAULT 0,
            dismissed     INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, due_at ASC);
        """)
    print("DB ready:", DB_PATH)


# ── Users ─────────────────────────────────────────────────────────────────────

def upsert_user(id, name, email, avatar, provider):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (id, name, email, avatar, provider)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name, avatar=excluded.avatar
        """, (id, name, email, avatar, provider))
    return get_user_by_email(email)


def get_user(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(email):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return dict(row) if row else None


# ── Conversations ─────────────────────────────────────────────────────────────

def create_conversation(conv_id, user_id, title="New conversation"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id, title) VALUES (?,?,?)",
            (conv_id, user_id, title)
        )
    return conv_id


def update_conversation_title(conv_id, title):
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET title=?, updated_at=datetime('now') WHERE id=?",
            (title[:80], conv_id)
        )


def touch_conversation(conv_id):
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET updated_at=datetime('now') WHERE id=?",
            (conv_id,)
        )


def get_conversations(user_id, limit=40):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, title, updated_at FROM conversations
            WHERE user_id=? ORDER BY updated_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def delete_conversation(conv_id, user_id):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM conversations WHERE id=? AND user_id=?",
            (conv_id, user_id)
        )


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(conv_id, role, content):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?,?,?)",
            (conv_id, role, content)
        )


def get_messages(conv_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC",
            (conv_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# ── Canvas config ──────────────────────────────────────────────────────────────

def save_canvas_config(user_id, canvas_url, canvas_token):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO canvas_config (user_id, canvas_url, canvas_token, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                canvas_url=excluded.canvas_url,
                canvas_token=excluded.canvas_token,
                updated_at=excluded.updated_at
        """, (user_id, canvas_url.rstrip("/"), canvas_token))


def get_canvas_config(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM canvas_config WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def delete_canvas_config(user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM canvas_config WHERE user_id=?", (user_id,))


# ── WhatsApp config ────────────────────────────────────────────────────────────

def save_whatsapp_config(user_id, phone, enabled=True):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO whatsapp_config (user_id, phone, enabled, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                phone=excluded.phone, enabled=excluded.enabled, updated_at=excluded.updated_at
        """, (user_id, phone, 1 if enabled else 0))


def get_whatsapp_config(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM whatsapp_config WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


# ── Reminders ──────────────────────────────────────────────────────────────────

def save_reminder(uid, item_id, item_type, title, course, due_at, urgency):
    import uuid as _uuid
    rid = str(_uuid.uuid4())
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO reminders
                (id, user_id, item_id, item_type, title, course, due_at, urgency)
            VALUES (?,?,?,?,?,?,?,?)
        """, (rid, uid, item_id, item_type, title, course, due_at, urgency))
    return rid


def get_reminders(user_id, include_dismissed=False):
    q = "SELECT * FROM reminders WHERE user_id=?"
    if not include_dismissed:
        q += " AND dismissed=0"
    q += " ORDER BY due_at ASC NULLS LAST"
    with get_conn() as conn:
        rows = conn.execute(q, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def mark_whatsapp_sent(reminder_id):
    with get_conn() as conn:
        conn.execute("UPDATE reminders SET whatsapp_sent=1 WHERE id=?", (reminder_id,))


def dismiss_reminder(reminder_id, user_id):
    with get_conn() as conn:
        conn.execute("UPDATE reminders SET dismissed=1 WHERE id=? AND user_id=?",
                     (reminder_id, user_id))


def delete_reminder(reminder_id, user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM reminders WHERE id=? AND user_id=?", (reminder_id, user_id))


if __name__ == "__main__":
    init_db()
