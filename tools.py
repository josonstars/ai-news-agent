# tools.py —— Agent 可调用的工具集（共 10 个）
import os
import json
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

from config import WORKSPACE_DIR
import db

WORKSPACE = Path(WORKSPACE_DIR).resolve()
for sub in ["prefs", "briefings", "cache", "outbox", "data"]:
    (WORKSPACE / sub).mkdir(parents=True, exist_ok=True)


def _safe(p: str) -> Path:
    if not p:
        p = "."
    raw = Path(p)
    path = (WORKSPACE / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not str(path).startswith(str(WORKSPACE)):
        raise ValueError(f"越权访问被拒绝: {p}")
    return path


# ============ 1. list_dir ============
def list_dir(path: str = ".") -> str:
    p = _safe(path)
    if not p.exists():
        return f"目录不存在：{path}"
    if not p.is_dir():
        return f"不是目录：{path}"
    items = []
    for e in sorted(p.iterdir()):
        if e.is_dir():
            items.append(f"[DIR]  {e.name}/")
        else:
            items.append(f"[FILE] {e.name}  ({e.stat().st_size} bytes)")
    return "\n".join(items) or "(空目录)"


# ============ 2. read_file ============
def read_file(path: str) -> str:
    p = _safe(path)
    if not p.exists():
        return f"文件不存在：{path}"
    if not p.is_file():
        return f"不是文件：{path}"
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"无法以 UTF-8 读取（可能是二进制）：{path}"
    return text[:20000] + (f"\n\n...(已截断，原文 {len(text)} 字符)"
                           if len(text) > 20000 else "")


# ============ 3. search_content ============
def search_content(keyword: str, dir: str = ".") -> str:
    p = _safe(dir)
    if not p.exists():
        return f"目录不存在：{dir}"
    hits = []
    exts = {".md", ".txt", ".json", ".log", ".csv", ".html"}
    for f in p.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in exts:
            continue
        try:
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if keyword.lower() in line.lower():
                    rel = f.relative_to(WORKSPACE)
                    hits.append(f"{rel}:{i}: {line.strip()[:160]}")
                    if len(hits) >= 50:
                        break
        except Exception:
            continue
        if len(hits) >= 50:
            break
    return "\n".join(hits) if hits else f"未找到包含 '{keyword}' 的内容"


# ============ 4. write_file ============
def write_file(path: str, content: str) -> str:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {p.relative_to(WORKSPACE)}（{len(content)} 字符）"


# ============ 5. bash ============
def bash(command: str) -> str:
    banned = ["rm -rf /", ":(){", "mkfs", "dd if=", "> /dev/sda"]
    for b in banned:
        if b in command:
            return f"命令被安全策略拒绝：包含危险片段 {b!r}"
    try:
        r = subprocess.run(command, shell=True, capture_output=True,
                           text=True, timeout=60, cwd=WORKSPACE)
    except subprocess.TimeoutExpired:
        return "命令超时（>60s）"
    out = (r.stdout or "") + (r.stderr or "")
    return out[:8000] if out.strip() else f"(无输出, exit={r.returncode})"


# ============ 6. web_search ============
RSS_FEEDS = {
    "HackerNews-AI": "https://hnrss.org/newest?q=AI",
    "TheVerge-AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "TechCrunch-AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "MIT-TechReview": "https://www.technologyreview.com/feed/",
}


def web_search(keyword: str = "*", limit: int = 8) -> str:
    results = []
    for name, url in RSS_FEEDS.items():
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 AI-News-Agent"})
            xml = urllib.request.urlopen(req, timeout=10).read()
            root = ET.fromstring(xml)
            for item in root.iter("item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = (item.findtext("description") or "").strip()[:200]
                if not title:
                    continue
                if keyword == "*" or keyword.lower() in (title + desc).lower():
                    results.append(
                        f"来源: {name}\n标题: {title}\n链接: {link}\n摘要: {desc}\n")
                if len(results) >= limit * 2:
                    break
        except Exception as e:
            results.append(f"[{name}] 抓取失败: {e}\n")
        if len(results) >= limit * 2:
            break
    return "\n".join(results[:limit]) if results else f"没有找到关于 '{keyword}' 的新闻"


# ============ 7. push_to_user ============
def push_to_user(user_id: str, content: str) -> str:
    outbox = WORKSPACE / "outbox"
    outbox.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    f = outbox / f"{user_id}_{ts}.txt"
    f.write_text(content, encoding="utf-8")
    return f"已推送给 {user_id}（Demo：写入 {f.relative_to(WORKSPACE)}）"


# ============ 8. get_date ============
def get_date() -> str:
    now = datetime.now()
    return (f"date: {now.strftime('%Y-%m-%d')}\n"
            f"time: {now.strftime('%H:%M:%S')}\n"
            f"weekday: {now.strftime('%A')}")


# ============ 9. save_briefing_to_db ============
def save_briefing_to_db(user_id: str, brief_date: str, content: str,
                        title: str = "", file_path: str = "") -> str:
    db.save_briefing(user_id, brief_date, content, title, file_path)
    return f"已写入数据库：{user_id} / {brief_date}"


# ============ 10. query_briefing_history ============
def query_briefing_history(user_id: str, limit: int = 10) -> str:
    rows = db.list_briefings(user_id, limit)
    if not rows:
        return f"{user_id} 还没有历史简报"
    return "\n".join(
        f"{r['brief_date']}  {r['title'] or '(无标题)'}  pushed={r['pushed']}"
        for r in rows)


# ============ 注册表 ============
TOOL_IMPL = {
    "list_dir": list_dir,
    "read_file": read_file,
    "search_content": search_content,
    "write_file": write_file,
    "bash": bash,
    "web_search": web_search,
    "push_to_user": push_to_user,
    "get_date": get_date,
    "save_briefing_to_db": save_briefing_to_db,
    "query_briefing_history": query_briefing_history,
}


# ============ Schema ============
TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "列出目录下的文件和子目录。",
        "parameters": {"type": "object",
            "properties": {"path": {"type": "string", "description": "相对 workspace 的路径"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取文件内容（读用户偏好、历史简报）。",
        "parameters": {"type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "search_content",
        "description": "在目录下按关键词搜索文件内容，用于去重。",
        "parameters": {"type": "object",
            "properties": {"keyword": {"type": "string"},
                           "dir": {"type": "string"}},
            "required": ["keyword", "dir"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "写文件。简报最终要写到这里。",
        "parameters": {"type": "object",
            "properties": {"path": {"type": "string"},
                           "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "bash",
        "description": "执行 shell 命令（curl/grep/date 等）。",
        "parameters": {"type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "搜索最新 AI 新闻，返回标题、链接、摘要。keyword='*' 表示不限关键词。",
        "parameters": {"type": "object",
            "properties": {"keyword": {"type": "string"},
                           "limit": {"type": "integer"}},
            "required": ["keyword"]}}},
    {"type": "function", "function": {
        "name": "push_to_user",
        "description": "推送简报给用户。",
        "parameters": {"type": "object",
            "properties": {"user_id": {"type": "string"},
                           "content": {"type": "string"}},
            "required": ["user_id", "content"]}}},
    {"type": "function", "function": {
        "name": "get_date",
        "description": "获取当前日期时间。",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "save_briefing_to_db",
        "description": "把简报写入数据库。",
        "parameters": {"type": "object",
            "properties": {"user_id": {"type": "string"},
                           "brief_date": {"type": "string", "description": "YYYY-MM-DD"},
                           "content": {"type": "string"},
                           "title": {"type": "string"},
                           "file_path": {"type": "string"}},
            "required": ["user_id", "brief_date", "content"]}}},
    {"type": "function", "function": {
        "name": "query_briefing_history",
        "description": "从数据库查该用户的历史简报。",
        "parameters": {"type": "object",
            "properties": {"user_id": {"type": "string"},
                           "limit": {"type": "integer"}},
            "required": ["user_id"]}}},
]