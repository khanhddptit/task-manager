from app.db import get_db


def get_task(workspace_id, project_id, task_id):
    return get_db().execute(
        """SELECT t.id, t.project_id, t.created_by, t.assignee_id,
                  t.updated_by, t.title, t.description, t.status,
                  t.due_date, t.created_at, t.updated_at
           FROM task AS t
           JOIN project AS p ON p.id = t.project_id
           WHERE p.workspace_id = ? AND t.project_id = ? AND t.id = ?""",
        (workspace_id, project_id, task_id),
    ).fetchone()


def list_tasks(project_id, status=None, assignee_id=None):
    conditions = ["project_id = ?"]
    parameters = [project_id]
    if status is not None:
        conditions.append("status = ?")
        parameters.append(status)
    if assignee_id is not None:
        conditions.append("assignee_id = ?")
        parameters.append(assignee_id)
    return get_db().execute(
        f"""SELECT id, project_id, created_by, assignee_id, updated_by,
                   title, description, status, due_date, created_at, updated_at
            FROM task
            WHERE {" AND ".join(conditions)}
            ORDER BY created_at DESC, id DESC""",
        parameters,
    ).fetchall()


def insert_task(project_id, user_id, values):
    cursor = get_db().execute(
        """INSERT INTO task
               (project_id, created_by, assignee_id, title, description,
                status, due_date, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            user_id,
            values.get("assignee_id"),
            values["title"],
            values.get("description", ""),
            values.get("status", "todo"),
            values.get("due_date"),
            user_id,
        ),
    )
    return cursor.lastrowid


def update_task(task_id, user_id, values):
    assignments = [f"{field} = ?" for field in values]
    parameters = list(values.values())
    assignments.extend(("updated_by = ?", "updated_at = CURRENT_TIMESTAMP"))
    parameters.extend((user_id, task_id))
    get_db().execute(
        f"UPDATE task SET {', '.join(assignments)} WHERE id = ?",
        parameters,
    )


def delete_task(task_id):
    get_db().execute("DELETE FROM task WHERE id = ?", (task_id,))


def is_project_member(project_id, user_id):
    return get_db().execute(
        "SELECT 1 FROM project_member WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone() is not None
