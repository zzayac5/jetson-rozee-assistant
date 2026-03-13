import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / "jetson-ui" / "tasks.db"

TASK_COLUMNS = {
    "task_number", "title", "description", "status",
    "created_by", "task_source", "raw_capture_text",
    "priority_user", "priority_ai", "importance_user", "importance_ai",
    "impact_user", "impact_ai", "urgency_user", "urgency_ai",
    "hard_deadline", "soft_deadline", "estimated_minutes_min", "estimated_minutes_max",
    "can_self_move", "needs_permission_to_move", "can_delegate", "can_outsource", "can_automate",
    "resource_required", "resource_status",
    "line_of_effort", "line_of_operation", "function", "category", "subcategory",
    "project", "context",
    "is_blocked", "blocking_reason", "depends_on_summary",
    "recurring", "recurrence_rule",
    "user_confirmed", "ai_enriched", "review_needed"
}

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}

def next_task_number() -> str:
    conn = get_conn()
    row = conn.execute("SELECT id FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    next_id = 1 if row is None else row["id"] + 1
    return f"TASK-{next_id:05d}"

def list_tasks(limit: int = 200) -> list[dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_task(task_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return None

    task = row_to_dict(row)
    task["people"] = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM task_people WHERE task_id = ?", (task_id,)
    ).fetchall()]
    task["subtasks"] = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM task_subtasks WHERE task_id = ?", (task_id,)
    ).fetchall()]
    task["resources"] = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM task_resources WHERE task_id = ?", (task_id,)
    ).fetchall()]
    task["dependencies"] = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM task_dependencies WHERE task_id = ?", (task_id,)
    ).fetchall()]
    task["inferences"] = [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM task_inferences WHERE task_id = ?", (task_id,)
    ).fetchall()]
    conn.close()
    return task

def create_task(data: dict[str, Any]) -> int:
    payload = {k: v for k, v in data.items() if k in TASK_COLUMNS}
    if "title" not in payload or not str(payload["title"]).strip():
        raise ValueError("title is required")

    if "task_number" not in payload or not payload["task_number"]:
        payload["task_number"] = next_task_number()

    cols = list(payload.keys())
    vals = [payload[c] for c in cols]

    conn = get_conn()
    sql = f"""
        INSERT INTO tasks ({", ".join(cols)})
        VALUES ({", ".join(["?"] * len(cols))})
    """
    cur = conn.execute(sql, vals)
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id

def update_task(task_id: int, data: dict[str, Any]) -> bool:
    payload = {k: v for k, v in data.items() if k in TASK_COLUMNS and k != "task_number"}
    if not payload:
        return False

    payload["updated_at"] = sqlite3.connect(":memory:").execute(
        "SELECT CURRENT_TIMESTAMP"
    ).fetchone()[0]

    cols = list(payload.keys())
    vals = [payload[c] for c in cols] + [task_id]

    conn = get_conn()
    sql = f"""
        UPDATE tasks
        SET {", ".join([f"{c} = ?" for c in cols])}
        WHERE id = ?
    """
    cur = conn.execute(sql, vals)
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed

def add_task_inference(task_id: int, field_name: str, inferred_value: str,
                       rationale: str | None = None, confidence: float | None = None,
                       needs_confirmation: int = 1) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO task_inferences
        (task_id, field_name, inferred_value, rationale, confidence, needs_confirmation)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (task_id, field_name, inferred_value, rationale, confidence, needs_confirmation)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id

def add_task_person(task_id: int, person_name: str, role: str | None = None,
                    involvement_type: str | None = None, required: int = 0,
                    source_type: str = "user_explicit") -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO task_people
        (task_id, person_name, role, involvement_type, required, source_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (task_id, person_name, role, involvement_type, required, source_type)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id

def add_subtask(task_id: int, title: str, status: str = "inbox",
                priority: int | None = None, source_type: str = "user_explicit") -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO task_subtasks
        (task_id, title, status, priority, source_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (task_id, title, status, priority, source_type)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id

def add_dependency(task_id: int, depends_on_task_number: str, dependency_type: str | None = None,
                   dependency_strength: str | None = None, source_type: str = "user_explicit",
                   notes: str | None = None) -> int:
    conn = get_conn()
    cur = conn.execute(
        """
        INSERT INTO task_dependencies
        (task_id, depends_on_task_number, dependency_type, dependency_strength, source_type, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (task_id, depends_on_task_number, dependency_type, dependency_strength, source_type, notes)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id
