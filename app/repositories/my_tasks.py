from app.core.db import get_db


def get_tasks_assigned_to_user(user_id):
    return get_db().execute(
        """SELECT t.id, t.project_id, p.name AS project_name,
                  p.workspace_id, w.name AS workspace_name,
                  t.title, t.status, t.priority, t.due_date,
                  t.sprint_id, s.name AS sprint_name,
                  t.created_at, t.updated_at,
                  u.id AS assignee_id, u.username AS assignee_username,
                  u.display_name AS assignee_display_name,
                  u.email AS assignee_email,
                  (u.avatar_path IS NOT NULL) AS assignee_has_avatar
           FROM task AS t
           JOIN project AS p ON p.id = t.project_id
           JOIN workspace AS w ON w.id = p.workspace_id
           JOIN user AS u ON u.id = t.assignee_id
           LEFT JOIN sprint AS s
               ON s.id = t.sprint_id AND s.project_id = t.project_id
           JOIN workspace_member AS wm
               ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           LEFT JOIN project_member AS pm
               ON pm.project_id = p.id
              AND pm.workspace_id = p.workspace_id
              AND pm.user_id = wm.user_id
           WHERE t.assignee_id = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)
           ORDER BY p.name COLLATE NOCASE, t.due_date IS NULL,
                    t.due_date, t.created_at DESC, t.id DESC""",
        (user_id, user_id),
    ).fetchall()
