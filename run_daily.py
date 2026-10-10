# run_daily.py —— 定时批处理：为每个用户生成简报
import json
import traceback
from pathlib import Path
from datetime import datetime

from config import WORKSPACE_DIR, ensure_dirs
from agent import run_agent

WS = Path(WORKSPACE_DIR)


def main():
    ensure_dirs()
    prefs_dir = WS / "prefs"
    if not prefs_dir.exists():
        print("还没有任何用户偏好文件，退出。")
        return

    for pf in sorted(prefs_dir.glob("*.json")):
        try:
            user = json.loads(pf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[跳过] 读取 {pf} 失败: {e}")
            continue
        uid = user.get("user_id")
        if not uid:
            print(f"[跳过] {pf} 缺少 user_id")
            continue

        print(f"\n=================== 生成 {uid} 的简报 ===================")
        try:
            final = run_agent(uid, verbose=True)
            print(f"[{uid}] 最终回答：{final}")
        except Exception:
            print(f"[{uid}] 运行失败：")
            traceback.print_exc()

    print(f"\n全部完成 @ {datetime.now()}")


if __name__ == "__main__":
    main()