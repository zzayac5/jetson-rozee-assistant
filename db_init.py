import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "jetson-ui" / "tasks.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'inbox',

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    created_by TEXT DEFAULT 'user',
    task_source TEXT,
    raw_capture_text TEXT,

    priority_user INTEGER,
    priority_ai INTEGER,
    importance_user INTEGER,
    importance_ai INTEGER,
    impact_user INTEGER,
    impact_ai INTEGER,
    urgency_user INTEGER,
    urgency_ai INTEGER,

    hard_deadline TEXT,
    soft_deadline TEXT,
    estimated_minutes_min INTEGER,
    estimated_minutes_max INTEGER,

    can_self_move INTEGER,
    needs_permission_to_move INTEGER,
    can_delegate INTEGER,
    can_outsource INTEGER,
    can_automate INTEGER,

    resource_required INTEGER,
    resource_status TEXT,

    line_of_effort TEXT,
    line_of_operation TEXT,
    function TEXT,
    category TEXT,
    subcategory TEXT,
    project TEXT,
    context TEXT,

    is_blocked INTEGER,
    blocking_reason TEXT,
    depends_on_summary TEXT,

    recurring INTEGER DEFAULT 0,
    recurrence_rule TEXT,

    user_confirmed INTEGER DEFAULT 0,
    ai_enriched INTEGER DEFAULT 0,
    review_needed INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS task_people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    person_name TEXT NOT NULL,
    role TEXT,
    involvement_type TEXT,
    required INTEGER DEFAULT 0,
    source_type TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_subtasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'inbox',
    priority INTEGER,
    source_type TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    resource_name TEXT NOT NULL,
    resource_type TEXT,
    resource_status TEXT,
    required_by_date TEXT,
    source_type TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    depends_on_task_number TEXT NOT NULL,
    dependency_type TEXT,
    dependency_strength TEXT,
    source_type TEXT,
    notes TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_inferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    inferred_value TEXT,
    rationale TEXT,
    confidence REAL,
    needs_confirmation INTEGER DEFAULT 1,
    confirmed_by_user INTEGER DEFAULT 0,
    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""

def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    print(f"Initialized database at: {DB_PATH}")

if __name__ == "__main__":
    main()
