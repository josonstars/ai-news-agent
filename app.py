# app.py —— Flask 前端
import json
from pathlib import Path
from flask import Flask, request, render_template, jsonify

from config import WORKSPACE_DIR, ensure_dirs
from agent import run_agent
import db

app = Flask(__name__)
WS = Path(WORKSPACE_DIR)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/prefs", methods=["POST"])
def save_prefs():
    ensure_dirs()
    data = request.get_json(force=True)
    uid = (data.get("user_id") or "").strip()
    if not uid:
        return jsonify({"ok": False, "msg": "user_id 不能为空"}), 400

    prefs = {
        "user_id": uid,
        "email": data.get("email", ""),
        "topics": data.get("topics", []),
        "keywords": data.get("keywords", []),
        "exclude": data.get("exclude", []),
        "push_channel": data.get("push_channel", "outbox"),
        "push_time": data.get("push_time", "08:30"),
    }
    (WS / "prefs").mkdir(parents=True, exist_ok=True)
    (WS / "prefs" / f"{uid}.json").write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2), encoding="utf-8")
    db.set_prefs(uid, prefs["topics"], prefs["keywords"], prefs["exclude"])
    db.upsert_user(uid, prefs["email"], prefs["push_channel"], prefs["push_time"])
    return jsonify({"ok": True, "msg": f"已保存 {uid} 的偏好"})


@app.route("/api/prefs/<uid>", methods=["GET"])
def get_prefs(uid):
    f = WS / "prefs" / f"{uid}.json"
    if not f.exists():
        return jsonify({"ok": False, "msg": "未找到偏好"}), 404
    return jsonify({"ok": True, "prefs": json.loads(f.read_text(encoding="utf-8"))})


@app.route("/api/run", methods=["POST"])
def run():
    data = request.get_json(force=True)
    uid = (data.get("user_id") or "").strip()
    if not uid:
        return jsonify({"ok": False, "msg": "user_id 不能为空"}), 400
    try:
        result = run_agent(uid, verbose=False)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/history/<uid>", methods=["GET"])
def history(uid):
    rows = db.list_briefings(uid, 30)
    if rows:
        items = []
        for r in rows:
            detail = db.get_briefing(uid, r["brief_date"])
            items.append({
                "name": r["file_path"] or f"{r['brief_date']}_{uid}.md",
                "brief_date": r["brief_date"],
                "title": r["title"] or "",
                "content": detail["content"] if detail else "",
            })
        return jsonify({"ok": True, "items": items})

    bdir = WS / "briefings"
    if not bdir.exists():
        return jsonify({"ok": True, "items": []})
    items = []
    for f in sorted(bdir.glob(f"*_{uid}.md"), reverse=True)[:30]:
        items.append({"name": f.name, "content": f.read_text(encoding="utf-8")})
    return jsonify({"ok": True, "items": items})


@app.route("/api/tool_calls/<uid>", methods=["GET"])
def tool_calls(uid):
    import sqlite3
    from config import DB_PATH
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    run = c.execute(
        "SELECT run_id FROM tool_call_log WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (uid,),
    ).fetchone()
    if not run:
        c.close()
        return jsonify({"ok": True, "run_id": "", "items": []})
    rid = run["run_id"]
    items = [dict(r) for r in c.execute(
        "SELECT step, tool_name, arguments FROM tool_call_log "
        "WHERE run_id=? ORDER BY step", (rid,))]
    c.close()
    return jsonify({"ok": True, "run_id": rid, "items": items})


if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=5000, debug=True)