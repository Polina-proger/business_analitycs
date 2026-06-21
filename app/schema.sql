CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    position TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_key TEXT NOT NULL,
    report_title TEXT NOT NULL,
    period_type TEXT NOT NULL,
    period_label TEXT NOT NULL,
    report_date TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    submitted_by INTEGER NOT NULL,
    submitted_by_name TEXT NOT NULL,
    submitted_by_position TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (submitted_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS dashboards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    platform TEXT NOT NULL,
    period_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_name TEXT NOT NULL,
    uploaded_by INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (uploaded_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS article_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);
