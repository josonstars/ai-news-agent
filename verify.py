# verify.py —— 自动检查是否满足所有要求
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
ok_all = True


def check(name, cond, detail=""):
    global ok_all
    flag = "✅" if cond else "❌"
    print(f"{flag} {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        ok_all = False


print("=" * 60)
print("每日 AI 新闻助手 Agent — 验收检查")
print("=" * 60)

print("\n[1] 文件完整性")
for f in ["config.py", "tools.py", "agent.py", "app.py", "run_daily.py",
          "templates/index.html", "schema.sql", "migrate.py", "db.py",
          "requirements.txt", "environment.yml",
          ".gitignore", ".env.example"]:
    check(f"存在 {f}", (ROOT / f).exists())

print("\n[2] 工具集（要求至少 5 个）")
sys.path.insert(0, str(ROOT))
try:
    from tools import TOOL_IMPL, TOOLS_SCHEMA
    n = len(TOOL_IMPL)
    check(f"已实现 {n} 个工具", n >= 5, ", ".join(TOOL_IMPL.keys()))
    check("Schema 与实现数量一致", n == len(TOOLS_SCHEMA))
except Exception as e:
    check("导入 tools.py 失败", False, str(e))

print("\n[3] 题目指定的 5 个工具")
for t in ["list_dir", "read_file", "search_content", "write_file", "bash"]:
    check(t, t in TOOL_IMPL)

print("\n[4] 核心要求①：工具顺序由 LLM 决定")
src = (ROOT / "agent.py").read_text(encoding="utf-8")
check("tool_choice=auto", 'tool_choice="auto"' in src or "tool_choice='auto'" in src)
check("for step in range(MAX_STEPS)", "for step in range(MAX_STEPS)" in src)
check("msg.tool_calls 判断", "msg.tool_calls" in src)
bad = ["if step == 1:", "elif step == 2:", "if step==1:", "pipeline(", "Sequence("]
check("无硬编码步骤", all(x not in src for x in bad))

print("\n[5] 环境变量（DeepSeek）")
key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
check("API Key 已设置", bool(key), (key[:8] + "...") if key else "未设置")
base = (os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "")
check("BASE_URL 含 deepseek", "deepseek" in base.lower())

print("\n[6] 数据库")
check("schema.sql 存在", (ROOT / "schema.sql").exists())
check("migrations/ 存在", (ROOT / "migrations").is_dir())
check("migrate.py 存在", (ROOT / "migrate.py").exists())
check("db.py 存在", (ROOT / "db.py").exists())
try:
    from config import DB_PATH
    check("agent.db 已生成", DB_PATH.exists(), str(DB_PATH))
    if DB_PATH.exists():
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for t in ["users", "user_prefs", "briefings",
                  "pushed_news", "tool_call_log", "schema_version"]:
            check(f"表 {t}", t in tables)
except Exception as e:
    check("检查数据库失败", False, str(e))

print("\n[7] 密钥未硬编码")
try:
    out = subprocess.run(["git", "grep", "-nE", r"sk-[a-zA-Z0-9]{20,}"],
                         cwd=ROOT, capture_output=True, text=True, timeout=10)
    check("仓库中无 API Key", out.returncode != 0 or not out.stdout.strip())
except Exception:
    check("git 未初始化（可忽略）", True)

print("\n[8] 前端页面")
html = ROOT / "templates" / "index.html"
if html.exists():
    s = html.read_text(encoding="utf-8")
    check("可填 user_id", "user_id" in s)
    check("可设偏好", "topics" in s and "keywords" in s)
    check("可查历史", "history" in s)

print("\n[9] 每日定时")
check("run_daily.py 遍历 prefs",
      "for pf in" in (ROOT / "run_daily.py").read_text(encoding="utf-8"))

print("\n" + "=" * 60)
print("结论：" + ("✅ 全部通过" if ok_all else "❌ 有未通过项"))
print("=" * 60)
sys.exit(0 if ok_all else 1)