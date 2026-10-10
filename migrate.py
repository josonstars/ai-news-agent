# migrate.py —— 数据库迁移执行器
import sqlite3
import sys
from pathlib import Path

from config import DB_PATH, ensure_dirs

ROOT = Path(__file__).parent
MIGRATIONS_DIR = ROOT / "migrations"
SCHEMA_FILE = ROOT / "schema.sql"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_version_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            description VARCHAR(255)
        )
    """)
    conn.commit()


def _applied_versions(conn):
    try:
        return {r[0] for r in conn.execute("SELECT version FROM schema_version")}
    except sqlite3.OperationalError:
        return set()


def apply_schema(conn):
    if SCHEMA_FILE.exists():
        conn.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
        conn.commit()
        print("[migrate] ✅ 已应用 schema.sql")


def apply_migrations(conn):
    applied = _applied_versions(conn)
    for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
        try:
            ver = int(f.stem.split("_", 1)[0])
        except (ValueError, IndexError):
            print(f"[migrate] 跳过无法解析版本号：{f.name}")
            continue
        if ver in applied:
            print(f"[migrate] 已应用 v{ver} {f.name}，跳过")
            continue
        try:
            conn.executescript(f.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version, description) VALUES(?,?)",
                (ver, f.name),
            )
            conn.commit()
            print(f"[migrate] ✅ 已应用 v{ver} {f.name}")
        except sqlite3.OperationalError as e:
            print(f"[migrate] ⚠️ v{ver} {f.name} 出错（可能已存在）：{e}")
            conn.rollback()


def main():
    if "--reset" in sys.argv:
        ans = input(f"⚠️ 删除 {DB_PATH} 并重建？输入 yes 继续：")
        if ans.strip().lower() != "yes":
            print("已取消。")
            return
        if DB_PATH.exists():
            DB_PATH.unlink()
        print(f"[migrate] 已删除 {DB_PATH}")

    ensure_dirs()
    conn = _conn()
    try:
        _ensure_version_table(conn)
        apply_schema(conn)
        apply_migrations(conn)
        print(f"[migrate] ✅ 完成。数据库：{DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()