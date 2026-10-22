from app.core.db import get_db


def get_sprint(workspace_id, project_id, sprint_id):
    return get_db().execute(
        """SELECT s.id, s.project_id, p.workspace_id, s.name, s.goal,
                  s.start_date, s.end_date, s.status, s.created_by,
                  s.updated_by, s.started_at, s.completed_at,
                  s.created_at, s.updated_at
           FROM sprint AS s
           JOIN project AS p ON p.id = s.project_id
           WHERE p.workspace_id = ? AND s.project_id = ? AND s.id = ?""",
        (workspace_id, project_id, sprint_id),
    ).fetchone()


def get_sprints_for_project(workspace_id, project_id):
    return get_db().execute(
        """SELECT s.id, s.project_id, p.workspace_id, s.name, s.goal,
                  s.start_date, s.end_date, s.status, s.created_by,
                  s.updated_by, s.started_at, s.completed_at,
                  s.created_at, s.updated_at,
                  COUNT(t.id) AS task_count,
                  SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done_count,
                  SUM(CASE WHEN t.status = 'review' THEN 1 ELSE 0 END) AS review_count,
                  SUM(CASE WHEN t.status != 'done' AND t.due_date < date('now')
                           THEN 1 ELSE 0 END) AS overdue_count
           FROM sprint AS s
           JOIN project AS p ON p.id = s.project_id
           LEFT JOIN task AS t ON t.sprint_id = s.id AND t.project_id = s.project_id
           WHERE p.workspace_id = ? AND s.project_id = ?
           GROUP BY s.id
           ORDER BY CASE s.status
                        WHEN 'active' THEN 0
                        WHEN 'planned' THEN 1
                        ELSE 2
                    END,
                    s.start_date DESC, s.id DESC""",
        (workspace_id, project_id),
    ).fetchall()


def insert_sprint(workspace_id, project_id, name, goal, start_date, end_date, created_by):
    cursor = get_db().execute(
        """INSERT INTO sprint
               (project_id, name, goal, start_date, end_date, created_by, updated_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (project_id, name, goal, start_date, end_date, created_by, created_by),
    )
    return cursor.lastrowid


def update_sprint(sprint_id, values, updated_by):
    columns = ("name", "goal", "start_date", "end_date")
    assignments = [f"{column} = ?" for column in columns if column in values]
    parameters = [values[column] for column in columns if column in values]
    assignments.extend(("updated_by = ?", "updated_at = CURRENT_TIMESTAMP"))
    parameters.extend((updated_by, sprint_id))
    get_db().execute(
        f"UPDATE sprint SET {', '.join(assignments)} WHERE id = ?",
        parameters,
    )


def set_sprint_status(sprint_id, status, updated_by):
    if status == "active":
        get_db().execute(
            """UPDATE sprint SET status = ?, started_at = CURRENT_TIMESTAMP,
                      completed_at = NULL, updated_by = ?,
                      updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, updated_by, sprint_id),
        )
    else:
        get_db().execute(
            """UPDATE sprint SET status = ?, completed_at = CURRENT_TIMESTAMP,
                      updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, updated_by, sprint_id),
        )


def count_active_sprints(project_id):
    return get_db().execute(
        "SELECT COUNT(*) FROM sprint WHERE project_id = ? AND status = 'active'",
        (project_id,),
    ).fetchone()[0]


def insert_sprint_task_event(sprint_id, task_id, event_type, status, actor_id):
    get_db().execute(
        """INSERT INTO sprint_task_history
               (sprint_id, task_id, event_type, status, changed_by)
           VALUES (?, ?, ?, ?, ?)""",
        (sprint_id, task_id, event_type, status, actor_id),
    )


def get_sprint_task_history(sprint_id):
    return get_db().execute(
        """SELECT id, sprint_id, task_id, event_type, status, changed_by,
                  occurred_at
           FROM sprint_task_history
           WHERE sprint_id = ?
           ORDER BY occurred_at ASC, id ASC""",
        (sprint_id,),
    ).fetchall()
