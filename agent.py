# agent.py —— ReAct / Function-Calling 循环
"""
★ 核心要求①：工具调用顺序由 LLM 决定
  整个文件只有一处 for 循环，没有任何"步骤 1 做 A、步骤 2 做 B"的硬编码。
  顺序、次数、何时停止，全部由模型在每一轮动态决定。
"""
import sys
import json
import time
from datetime import date
from openai import OpenAI

from config import (OPENAI_API_KEY, OPENAI_BASE_URL, MODEL,
                    MAX_STEPS, REQUEST_TIMEOUT, MAX_RETRIES, mask)
from tools import TOOLS_SCHEMA, TOOL_IMPL
import db


if not OPENAI_API_KEY:
    print("❌ 未检测到 API Key！")
    print("   Windows:  setx DEEPSEEK_API_KEY \"sk-你的key\"")
    print("   或在本项目根目录放 .env 文件写 DEEPSEEK_API_KEY=sk-xxx")
    print("   设置后请【完全重开】PyCharm。")
    sys.exit(1)

print(f"[config] BASE_URL = {OPENAI_BASE_URL}")
print(f"[config] MODEL    = {MODEL}")
print(f"[config] KEY      = {mask(OPENAI_API_KEY)}")


client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL,
    timeout=REQUEST_TIMEOUT,
    max_retries=MAX_RETRIES,
)


SYSTEM_PROMPT = """你是「每日 AI 新闻助手」Agent，负责为指定用户生成一份 AI 新闻简报并推送。

# 你的可用工具
- list_dir(path)                     列出目录
- read_file(path)                    读文件（读用户偏好、历史简报）
- search_content(keyword, dir)       在目录里按关键词搜索（去重）
- write_file(path, content)          写文件（写简报）
- bash(command)                      执行 shell 命令（curl/grep/date 等）
- web_search(keyword, limit)         搜索最新 AI 新闻
- push_to_user(user_id, content)     推送简报给用户
- get_date()                         取当前日期时间
- save_briefing_to_db(...)           把简报写入数据库
- query_briefing_history(user_id)    从数据库查历史简报

# 用户偏好位置
workspace/prefs/{user_id}.json 里有该用户关注的话题(topic)和关键词(keyword)。
workspace/briefings/ 下是历史简报。

# 你的目标
1. 生成 {today} 的 AI 新闻简报，内容必须匹配用户偏好。
2. 避免重复推送历史简报已经出现过的新闻（用 search_content 或 query_briefing_history 检查）。
3. 简报用 Markdown 写成，保存到 workspace/briefings/{today}_{user_id}.md，同时 save_briefing_to_db。
4. 简报结构：标题 + 日期 + 按话题分组的新闻（每条含标题/一句话摘要/链接/为什么值得关注）。
5. 生成后用 push_to_user 推送。
6. 最后用一段话告诉用户：简报路径、入库结果、推送结果。

# 工作方式（★ 重要）
你**不需要按固定步骤走**。每一步由你判断"我现在缺什么信息"，然后选最合适的工具。
- 先读偏好 → 再搜新闻 → 搜不到就换关键词 → 写简报前先查重 → 写完后可自检 → 推送
- 也可以一次调用多个工具（并行），例如同时用不同关键词调 web_search
- 如果你觉得某个工具没必要用，就别用

# 硬性规则
- 不要臆造新闻。所有新闻内容必须来自 web_search / bash 的真实返回。
- 每次工具调用后先想结果够不够用，不够就继续，够用就写简报。
- 简报完成后，输出一句话总结，不要再调用任何工具。
- 最多工作 {max_steps} 步。
"""


def run_agent(user_id: str, verbose: bool = True) -> str:
    today = date.today().isoformat()
    run_id = db.new_run_id()

    if verbose:
        print(f"\n[agent] run_id = {run_id}")
        print(f"[agent] today  = {today}")
        print(f"[agent] user   = {user_id}")

    messages = [
        {"role": "system",
         "content": SYSTEM_PROMPT.format(today=today, user_id=user_id,
                                         max_steps=MAX_STEPS)},
        {"role": "user",
         "content": f"请为 {user_id} 生成 {today} 的 AI 新闻简报，并推送。"},
    ]

    for step in range(MAX_STEPS):
        if verbose:
            print(f"\n===== Step {step + 1} / {MAX_STEPS} =====")

        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",   # ★ 让模型自己决定
                temperature=0.3,
            )
        except Exception as e:
            print(f"\n❌ 调用模型失败：{type(e).__name__}: {e}")
            raise

        msg = resp.choices[0].message
        messages.append(msg)

        # --- 情况 A：模型不再调工具 → 收工 ---
        if not msg.tool_calls:
            if verbose:
                print(f"[agent] 第 {step + 1} 步：模型自主停止")
            return msg.content or "(无输出)"

        # --- 情况 B：模型要求调工具 ---
        if verbose and msg.content:
            print(f"[agent] 思考: {msg.content[:200]}")

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if verbose:
                preview = json.dumps(args, ensure_ascii=False)
                print(f"[agent] 调用 {name}({preview[:200]})")

            t0 = time.time()
            fn = TOOL_IMPL.get(name)
            try:
                result = fn(**args) if fn else f"未知工具：{name}"
            except TypeError as e:
                result = f"参数错误：{e}"
            except Exception as e:
                result = f"工具执行异常：{type(e).__name__}: {e}"
            dt_ms = int((time.time() - t0) * 1000)
            result_str = str(result)

            if verbose:
                print(f"[agent] 返回: {result_str[:300]}")

            db.log_tool_call(run_id, user_id, step + 1, name,
                             args, result_str, dt_ms, MODEL)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str[:8000],
            })

    return "⚠️ 达到最大步数仍未完成。"


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "alice"
    final = run_agent(uid, verbose=True)
    print("\n=========== 最终回答 ===========")
    print(final)