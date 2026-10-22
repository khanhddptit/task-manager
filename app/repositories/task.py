from app.core.db import get_db


def get_project_access_context(workspace_id, project_id, actor_id):
    return get_db().execute(
        """SELECT p.id, p.workspace_id,
                  pm.role AS project_role,
                  wm.role AS workspace_role
           FROM project AS p
           LEFT JOIN project_member AS pm
               ON pm.project_id = p.id AND pm.user_id = ?
           LEFT JOIN workspace_member AS wm
               ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           WHERE p.id = ? AND p.workspace_id = ?""",
        (actor_id, actor_id, project_id, workspace_id),
    ).fetchone()


def insert_task(
    project_id, actor_id, title, description, assignee_id, status, due_date,
    priority="medium", sprint_id=None,
):
    db = get_db()
    position = db.execute(
        "SELECT COALESCE(MAX(position) + 1, 0) FROM task "
        "WHERE project_id = ? AND status = ?",
        (project_id, status),
    ).fetchone()[0]
    cursor = db.execute(
        """INSERT INTO task
               (project_id, created_by, assignee_id, updated_by, title,
                description, status, priority, sprint_id, position, due_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            actor_id,
            assignee_id,
            actor_id,
            title,
            description,
            status,
            priority,
            sprint_id,
            position,
            due_date,
        ),
    )
    return cursor.lastrowid


def get_task_by_id(workspace_id, project_id, task_id):
    return get_db().execute(
        """SELECT t.id, t.project_id, p.workspace_id, t.created_by,
                  t.assignee_id, t.updated_by, t.title, t.description,
                  t.status, t.priority, t.sprint_id, t.position, t.due_date,
                  t.created_at, t.updated_at
           FROM task AS t
           JOIN project AS p ON p.id = t.project_id
           WHERE p.workspace_id = ? AND t.project_id = ? AND t.id = ?""",
        (workspace_id, project_id, task_id),
    ).fetchone()


def get_tasks_for_project(workspace_id, project_id, status=None, assignee_id=None):
    conditions = ["p.workspace_id = ?", "t.project_id = ?"]
    parameters = [workspace_id, project_id]
    if status is not None:
        conditions.append("t.status = ?")
        parameters.append(status)
    if assignee_id is not None:
        conditions.append("t.assignee_id = ?")
        parameters.append(assignee_id)
    return get_db().execute(
        f"""SELECT t.id, t.project_id, p.workspace_id, t.created_by,
                   t.assignee_id, t.updated_by, t.title, t.description,
                   t.status, t.priority, t.sprint_id, t.position, t.due_date,
                   t.created_at, t.updated_at
            FROM task AS t
            JOIN project AS p ON p.id = t.project_id
            WHERE {" AND ".join(conditions)}
            ORDER BY t.status, t.position, t.id""",
        parameters,
    ).fetchall()


def reorder_project_tasks(workspace_id, project_id, ordered_ids_by_status, updated_by):
    db = get_db()
    for status, task_ids in ordered_ids_by_status.items():
        for position, task_id in enumerate(task_ids):
            db.execute(
                """UPDATE task
                   SET status = ?, position = ?,
                       updated_by = CASE WHEN status != ? THEN ? ELSE updated_by END,
                       updated_at = CASE WHEN status != ?
                                         THEN CURRENT_TIMESTAMP ELSE updated_at END
                   WHERE id = ? AND project_id = ?
                     AND project_id IN (
                         SELECT id FROM project WHERE workspace_id = ?
                     )""",
                (
                    status, position, status, updated_by, status,
                    task_id, project_id, workspace_id,
                ),
            )


def project_member_exists(project_id, user_id):
    return get_db().execute(
        """SELECT 1 FROM project_member
           WHERE project_id = ? AND user_id = ?""",
        (project_id, user_id),
    ).fetchone() is not None


def update_task(workspace_id, project_id, task_id, changes, updated_by):
    columns = (
        "title", "description", "assignee_id", "status", "priority",
        "sprint_id", "due_date"
    )
    assignments = [f"{column} = ?" for column in columns if column in changes]
    parameters = [changes[column] for column in columns if column in changes]
    assignments.extend(("updated_by = ?", "updated_at = CURRENT_TIMESTAMP"))
    parameters.extend((updated_by, task_id, project_id, workspace_id))
    get_db().execute(
        f"""UPDATE task SET {", ".join(assignments)}
            WHERE id = ? AND project_id = ?
              AND project_id IN (
                  SELECT id FROM project WHERE workspace_id = ?
              )""",
        parameters,
    )


def delete_task(workspace_id, project_id, task_id):
    cursor = get_db().execute(
        """DELETE FROM task
           WHERE id = ? AND project_id = ?
             AND project_id IN (
                 SELECT id FROM project WHERE workspace_id = ?
             )""",
        (task_id, project_id, workspace_id),
    )
    return cursor.rowcount
