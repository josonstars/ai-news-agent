# 每日 AI 新闻助手 Agent

一个每天自动为用户整理 AI 新闻简报并推送的 Agent。
**工具调用顺序由 LLM 自主决定**（ReAct / Function-Calling 循环），不是硬编码的线性流程。

---

## 一、项目简介

本项目实现了一个「每日 AI 新闻助手」Agent，具备以下能力：

- 用户可设置订阅偏好（关注话题、关键词、排除词）
- Agent 每天自动搜索最新 AI 新闻，按用户偏好筛选
- 自动去重（避免重复推送历史简报已出现过的新闻）
- 生成 Markdown 格式简报，保存到文件、写入数据库、推送给用户
- 提供 Web 前端：填身份 / 设偏好 / 一键生成 / 查看历史 / 查看工具调用序列

**核心特色**：工具调用顺序完全由 LLM 在运行时动态决定，代码里没有任何 `if step == 1: xxx elif step == 2: yyy` 的顺序硬编码。

---

## 二、技术栈

| 类别 | 技术 |
|---|---|
| 语言 | Python 3.11 |
| LLM | OpenAI SDK（兼容 DeepSeek / 阿里百炼 / 月之暗面 / 智谱 / 硅基流动等） |
| 默认模型 | DeepSeek `deepseek-chat` |
| 前端 | Flask + 原生 HTML/CSS/JS |
| 数据库 | SQLite 3（含 migration 脚本） |
| 环境管理 | conda（`environment.yml`） + pip（`requirements.txt`） |
| 版本管理 | Git |

---

## 三、目录结构

```
ai-news-agent/
├── .gitignore                    # Git 忽略规则
├── .env.example                  # 环境变量模板
├── .env                          # 真实密钥（本地，不提交）
├── README.md                     # 本文档
│
├── requirements.txt              # pip 依赖清单
├── environment.yml               # conda 环境定义
├── setup.bat                     # Windows 一键起环境
├── setup.sh                      # Mac/Linux 一键起环境
│
├── schema.sql                    # 数据库建表 SQL
├── migrate.py                    # migration 执行器
├── db.py                         # 数据库访问层
├── migrations/
│   ├── 001_init.sql
│   └── 002_add_model_name.sql
│
├── config.py                     # 配置（读环境变量）
├── tools.py                      # ★ 工具集（10 个）+ Function Schema
├── agent.py                      # ★ ReAct / Function-Calling 循环
├── app.py                        # Flask 前端
├── run_daily.py                  # 定时批处理入口
├── verify.py                     # 验收自检脚本
│
├── templates/
│   └── index.html                # 前端页面
│
└── workspace/                    # 运行时自动生成
    ├── prefs/                    # 用户偏好 JSON
    ├── briefings/                # 历史简报 Markdown
    ├── cache/                    # 去重缓存
    ├── outbox/                   # 推送内容
    └── data/agent.db             # SQLite 数据库
```

---

## 四、快速开始

### 4.1 一键起环境

**Windows**：双击 `setup.bat`

**Mac / Linux**：
```bash
bash setup.sh
```

**手动方式**：
```bash
conda env create -f environment.yml
conda activate ai-news
pip install -r requirements.txt
python migrate.py
```

### 4.2 配置密钥（走环境变量，绝不硬编码）

**方式 A（推荐）：复制 `.env` 并填写**

```bash
copy .env.example .env          # Windows
cp   .env.example .env          # Mac/Linux
```

编辑 `.env`，把 `DEEPSEEK_API_KEY` 换成你的真实 key：

```bash
DEEPSEEK_API_KEY=sk-你的真实key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

**方式 B：系统环境变量**

```cmd
setx DEEPSEEK_API_KEY "sk-你的真实key"
```
设置后需**完全重启终端 / IDE**。

**API Key 申请**：https://platform.deepseek.com

> 本项目使用任何 OpenAI 兼容接口都可以。换成阿里百炼、月之暗面、智谱、硅基流动时，只需修改 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`。

### 4.3 初始化数据库

```bash
python migrate.py
```

会创建 `workspace/data/agent.db`，包含 6 张表。

### 4.4 命令行运行 Agent

```bash
python agent.py alice
```

控制台会打印每一步的工具调用日志（`===== Step N =====`），可以直观看到 LLM 自主决策的过程。

### 4.5 启动前端

```bash
python app.py
```

浏览器打开 http://localhost:5000

页面功能：

1. 填 user_id、邮箱、话题、关键词、排除词
2. 点「保存偏好」写入文件和数据库
3. 点「让 Agent 开始工作」触发一次生成
4. 查看历史简报
5. 查看最近一次运行的工具调用序列

### 4.6 定时运行（Windows 任务计划程序）

1. `Win + R` → `taskschd.msc`
2. 创建基本任务 → 每天 08:30
3. 程序：`C:\Users\<你>\.conda\envs\ai-news\python.exe`
4. 参数：`"项目路径\run_daily.py"`
5. 起始于：项目根目录

Mac / Linux 用 crontab：

```bash
30 8 * * * cd /path/to/ai-news-agent && conda run -n ai-news python run_daily.py
```

---

## 五、核心设计

### 5.1 工具调用顺序由 LLM 决定

`agent.py` 里**只有一个 `for` 循环**，没有任何顺序硬编码：

```python
for step in range(MAX_STEPS):
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS_SCHEMA,
        tool_choice="auto",         # ← 模型自己挑工具
        temperature=0.3,
    )
    msg = resp.choices[0].message
    messages.append(msg)

    if not msg.tool_calls:          # ← 模型不调工具就收工
        return msg.content

    for tc in msg.tool_calls:       # ← 执行模型点名的工具
        result = TOOL_IMPL[tc.function.name](**json.loads(tc.function.arguments))
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
```

**循环里只做三件事**：

1. 调模型
2. 执行模型返回的 `tool_calls`
3. 把结果塞回 messages，再调模型

**顺序、次数、何时停止，全部由模型在每一轮动态决定。**

**三重证据**：

1. **源码证据**：`agent.py` 里只有一处 `for` 循环，`tool_choice="auto"`
2. **运行证据**：跑两次 `python agent.py alice`，工具序列不同
3. **数据库证据**：`tool_call_log` 表记录每次运行每步调用，`run_id` 每次不同

### 5.2 工具集（共 10 个）

| 工具 | 说明 |
|---|---|
| `list_dir(path)` | 列目录 |
| `read_file(path)` | 读文件 |
| `search_content(keyword, dir)` | 关键词搜索（去重） |
| `write_file(path, content)` | 写文件 |
| `bash(command)` | 执行 shell 命令 |
| `web_search(keyword, limit)` | 搜索最新 AI 新闻（RSS） |
| `push_to_user(user_id, content)` | 推送简报给用户 |
| `get_date()` | 获取当前日期时间 |
| `save_briefing_to_db(...)` | 简报写入数据库 |
| `query_briefing_history(user_id)` | 从数据库查历史简报 |

题目要求的 5 个（`list_dir` / `read_file` / `search_content` / `write_file` / `bash`）全部实现，另加 5 个业务工具。

### 5.3 系统提示词（节选）

```
# 你的目标
1. 生成 {today} 的 AI 新闻简报，内容必须匹配用户偏好。
2. 避免重复推送历史简报出现过的新闻。
3. 保存到 workspace/briefings/{today}_{user_id}.md，同时入库。
4. 生成后推送给用户。
5. 最后一段话总结。

# 工作方式（★ 重要）
你不需要按固定步骤走。每一步由你判断"我现在缺什么信息"，然后选最合适的工具。
- 先读偏好 → 再搜新闻 → 搜不到就换关键词 → 写简报前先查重 → 推送
- 也可以一次调用多个工具（并行）
- 如果你觉得某个工具没必要用，就别用

# 硬性规则
- 不要臆造新闻，所有内容必须来自 web_search / bash 的真实返回。
- 最多工作 {max_steps} 步。
```

提示词里写的是**目标 + 约束 + 参考思路**，不写"第一步做什么、第二步做什么"。

---

## 六、数据库设计

### 6.1 表结构

| 表 | 用途 |
|---|---|
| `users` | 用户基本信息（user_id、邮箱、推送渠道、推送时间） |
| `user_prefs` | 订阅偏好（话题 / 关键词 / 排除词） |
| `briefings` | 历史简报（含全文、文件路径、推送状态） |
| `pushed_news` | 已推送新闻标题（去重） |
| `tool_call_log` | **工具调用日志（顺序由 LLM 决定的证据）** |
| `schema_version` | migration 版本记录 |

### 6.2 Migration

- `schema.sql`：完整 DDL
- `migrations/001_init.sql`、`002_add_model_name.sql`：增量迁移脚本
- `migrate.py`：migration 执行器，幂等，可重复运行

```bash
python migrate.py            # 应用所有未应用的 migration
python migrate.py --reset    # 删库重建（危险，仅开发用）
```

### 6.3 查看工具调用序列（核心证据）

```bash
python -c "import sqlite3; c=sqlite3.connect('workspace/data/agent.db'); c.row_factory=sqlite3.Row; rid=c.execute('SELECT run_id FROM tool_call_log ORDER BY id DESC LIMIT 1').fetchone()['run_id']; print('run_id =', rid); [print(f\"  step {r['step']}: {r['tool_name']}\") for r in c.execute('SELECT step,tool_name FROM tool_call_log WHERE run_id=? ORDER BY step',(rid,))]"
```

输出示例：

```
run_id = a1b2c3d4e5f6
  step 1: read_file
  step 2: web_search
  step 3: web_search
  step 4: search_content
  step 5: write_file
  step 6: save_briefing_to_db
  step 7: push_to_user
```

**再跑一次，序列会不同** —— 这就是"顺序由 LLM 决定"的硬证据。

---

## 七、配置说明

所有配置项都从环境变量读取，绝不硬编码：

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 无（必填） | API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | API 端点 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `MAX_STEPS` | `25` | 单次运行最大步数（保险丝） |
| `REQUEST_TIMEOUT` | `60` | 单次请求超时（秒） |
| `MAX_RETRIES` | `2` | 请求失败重试次数 |
| `WORKSPACE_DIR` | `./workspace` | 工作区目录 |
| `DB_PATH` | `./workspace/data/agent.db` | 数据库文件路径 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | 空 | 邮件推送（可选） |

本地开发用 `.env` 文件（已在 `.gitignore` 中屏蔽），生产环境用系统环境变量。

---

## 八、安全说明

- **密钥全部走环境变量**：代码里没有任何硬编码的 API Key
- **`.env` 不提交**：`.gitignore` 已屏蔽 `.env`、`*.key`、`*.pem`
- **路径沙箱**：所有文件工具限制在 `workspace/` 内，防止路径穿越
- **bash 白名单**：拦截 `rm -rf /`、`mkfs`、`dd if=` 等危险命令
- **上下文截断**：工具返回结果超长时截断到 8000 字符，防止上下文爆炸

**自查命令**：

```bash
git grep -nE "sk-[a-zA-Z0-9]{20,}"        # 应无输出
git check-ignore -v .env                   # 应输出 .gitignore 行
```

---

## 九、验收

```bash
python verify.py
```

输出 `结论：✅ 全部通过` 即符合所有要求。

`verify.py` 检查项：

- 文件完整性（23 个关键文件）
- 工具数量 ≥ 5，Schema 与实现一致
- 题目指定 5 个工具（list_dir / read_file / search_content / write_file / bash）已实现
- **核心要求①**：`agent.py` 里 `tool_choice="auto"`、`for step in range(MAX_STEPS)`、`msg.tool_calls`，且无硬编码步骤
- 环境变量配置正确
- 数据库 6 张表存在
- 仓库无硬编码密钥
- 前端页面具备填身份 / 设偏好 / 查历史
- `run_daily.py` 遍历用户偏好

---

## 十、Git 版本管理

```bash
git log --oneline --graph
```

提交历史按功能模块分步：

```
* test: 添加验收自检脚本
* feat: Flask 前端与定时批处理
* feat: Agent ReAct 循环与 10 个工具
* feat(db): 添加数据库 schema 与 migration
* build: 添加依赖清单与一键起环境脚本
* chore: 初始化仓库，添加忽略规则与模板
```

---

## 十一、常见问题

| 报错 | 原因 | 解决 |
|---|---|---|
| `未检测到 API Key` | 环境变量没读到 | 用 `.env`，或重启 IDE |
| `openai.AuthenticationError` | key 不对 | 检查 `.env` 内容 |
| `ConnectTimeout` | 网络 / BASE_URL 错 | 改成 `https://api.deepseek.com/v1` |
| `ModuleNotFoundError: openai` | 解释器选错 | 切到 `ai-news` 环境 |
| `sqlite3.OperationalError: no such table` | 没跑 migrate | `python migrate.py` |
| `Address already in use` | 端口被占 | 关掉旧 `app.py` |

---

## 十二、License

MIT