-- schema.sql —— 每日 AI 新闻助手 Agent 数据库结构（SQLite）
PRAGMA foreign_keys = ON;

-- ============ 1. 用户表 ============
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      VARCHAR(64)  NOT NULL UNIQUE,
    email        VARCHAR(255),
    push_channel VARCHAR(32)  NOT NULL DEFAULT 'outbox',
    push_time    VARCHAR(8)   NOT NULL DEFAULT '08:30',
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);

-- ============ 2. 用户订阅偏好 ============
CREATE TABLE IF NOT EXISTS user_prefs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    VARCHAR(64)  NOT NULL,
    kind       VARCHAR(16)  NOT NULL,
    value      VARCHAR(128) NOT NULL,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, kind, value)
);
CREATE INDEX IF NOT EXISTS idx_prefs_user_kind ON user_prefs(user_id, kind);

-- ============ 3. 简报表 ============
CREATE TABLE IF NOT EXISTS briefings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     VARCHAR(64)  NOT NULL,
    brief_date  DATE         NOT NULL,
    title       VARCHAR(255),
    content     TEXT         NOT NULL,
    file_path   VARCHAR(512),
    pushed      INTEGER      NOT NULL DEFAULT 0,
    pushed_at   TIMESTAMP,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, brief_date)
);
CREATE INDEX IF NOT EXISTS idx_brief_user_date ON briefings(user_id, brief_date DESC);

-- ============ 4. 已推送新闻（去重）============
CREATE TABLE IF NOT EXISTS pushed_news (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    VARCHAR(64)  NOT NULL,
    title      VARCHAR(512) NOT NULL,
    url        VARCHAR(1024),
    source     VARCHAR(64),
    pushed_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pushed_user_title ON pushed_news(user_id, title);

-- ============ 5. 工具调用日志（★ 证明工具顺序由 LLM 决定）============
CREATE TABLE IF NOT EXISTS tool_call_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         VARCHAR(64) NOT NULL,
    user_id        VARCHAR(64) NOT NULL,
    step           INTEGER     NOT NULL,
    tool_name      VARCHAR(64) NOT NULL,
    arguments      TEXT,
    result_preview TEXT,
    duration_ms    INTEGER,
    created_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tcl_run ON tool_call_log(run_id, step);

-- ============ 6. Schema 版本 ============
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description VARCHAR(255)
);