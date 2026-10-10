# db.py —— 数据库访问层
import json
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Optional, List, Dict

from config import DB_PATH, ensure_dirs


@contextmanager
def get_conn():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- users ----------
def upsert_user(user_id: str, email: str = "",
                push_channel: str = "outbox", push_time: str = "08:30"):
    with get_conn() as c:
        c.execute("""
            INSERT INTO users(user_id, email, push_channel, push_time)
            VALUES(?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              email=excluded.email,
              push_channel=excluded.push_channel,
              push_time=excluded.push_time,
              updated_at=CURRENT_TIMESTAMP
        """, (user_id, email, push_channel, push_time))


def get_user(user_id: str) -> Optional[Dict]:
    with get_conn() as c:
        r = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(r) if r else None


# ---------- prefs ----------
def set_prefs(user_id: str, topics, keywords, excludes):
    upsert_user(user_id)
    with get_conn() as c:
        c.execute("DELETE FROM user_prefs WHERE user_id=?", (user_id,))
        rows = ([("topic", t) for t in topics]
                + [("keyword", k) for k in keywords]
                + [("exclude", e) for e in excludes])
        c.executemany(
            "INSERT OR IGNORE INTO user_prefs(user_id, kind, value) VALUES(?,?,?)",
            [(user_id, k, v) for k, v in rows],
        )


def get_prefs(user_id: str) -> Dict[str, List[str]]:
    with get_conn() as c:
        rows = c.execute(
            "SELECT kind, value FROM user_prefs WHERE user_id=?", (user_id,)
        ).fetchall()
    out = {"topics": [], "keywords": [], "exclude": []}
    m = {"topic": "topics", "keyword": "keywords", "exclude": "exclude"}
    for r in rows:
        out[m[r["kind"]]].append(r["value"])
    return out


# ---------- briefings ----------
def save_briefing(user_id: str, brief_date: str, content: str,
                  title: str = "", file_path: str = ""):
    upsert_user(user_id)
    with get_conn() as c:
        c.execute("""
            INSERT INTO briefings(user_id, brief_date, title, content, file_path)
            VALUES(?,?,?,?,?)
            ON CONFLICT(user_id, brief_date) DO UPDATE SET
              title=excluded.title,
              content=excluded.content,
              file_path=excluded.file_path
        """, (user_id, brief_date, title, content, file_path))


def list_briefings(user_id: str, limit: int = 30) -> List[Dict]:
    with get_conn() as c:
        rows = c.execute("""
            SELECT id, brief_date, title, file_path, pushed, created_at
            FROM briefings WHERE user_id=?
            ORDER BY brief_date DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        return [dict(r) for r in rows]


def get_briefing(user_id: str, brief_date: str) -> Optional[Dict]:
    with get_conn() as c:
        r = c.execute(
            "SELECT * FROM briefings WHERE user_id=? AND brief_date=?",
            (user_id, brief_date),
        ).fetchone()
        return dict(r) if r else None


def mark_pushed(user_id: str, brief_date: str):
    with get_conn() as c:
        c.execute("""
            UPDATE briefings SET pushed=1, pushed_at=CURRENT_TIMESTAMP
            WHERE user_id=? AND brief_date=?
        """, (user_id, brief_date))


# ---------- pushed_news ----------
def is_news_pushed(user_id: str, title: str) -> bool:
    with get_conn() as c:
        r = c.execute(
            "SELECT 1 FROM pushed_news WHERE user_id=? AND title=? LIMIT 1",
            (user_id, title),
        ).fetchone()
        return r is not None


def add_pushed_news(user_id: str, title: str, url: str = "", source: str = ""):
    upsert_user(user_id)
    with get_conn() as c:
        c.execute(
            "INSERT INTO pushed_news(user_id, title, url, source) VALUES(?,?,?,?)",
            (user_id, title, url, source),
        )


# ---------- tool_call_log ----------
def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def log_tool_call(run_id: str, user_id: str, step: int, tool_name: str,
                  arguments: dict, result_preview: str, duration_ms: int,
                  model_name: str = ""):
    try:
        upsert_user(user_id)
        with get_conn() as c:
            c.execute("""
                INSERT INTO tool_call_log
                  (run_id, user_id, step, tool_name, arguments,
                   result_preview, duration_ms, model_name)
                VALUES(?,?,?,?,?,?,?,?)
            """, (run_id, user_id, step, tool_name,
                  json.dumps(arguments, ensure_ascii=False),
                  result_preview[:500], duration_ms, model_name))
    except Exception as e:
        print(f"[db] 记录工具调用失败：{e}")


def list_tool_calls(run_id: str) -> List[Dict]:
    with get_conn() as c:
        rows = c.execute("""
            SELECT step, tool_name, arguments, duration_ms, created_at
            FROM tool_call_log WHERE run_id=? ORDER BY step, id
        """, (run_id,)).fetchall()
        return [dict(r) for r in rows]