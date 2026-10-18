from app.db import get_db


def insert_project(workspace_id, name, description, created_by):
    cursor = get_db().execute(
        """INSERT INTO project (workspace_id, name, description, created_by)
           VALUES (?, ?, ?, ?)""",
        (workspace_id, name, description, created_by),
    )
    return cursor.lastrowid


def get_project(workspace_id, project_id):
    return get_db().execute(
        """SELECT id, workspace_id, name, description, created_by,
                  updated_by, created_at, updated_at
           FROM project
           WHERE workspace_id = ? AND id = ?""",
        (workspace_id, project_id),
    ).fetchone()


def get_project_for_user(workspace_id, project_id, user_id):
    return get_db().execute(
        """SELECT p.id, p.workspace_id, p.name, p.description,
                  p.created_by, p.updated_by, p.created_at, p.updated_at,
                  CASE WHEN wm.role = 'owner' THEN 'admin' ELSE pm.role END AS role
           FROM project AS p
           JOIN workspace_member AS wm
             ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           LEFT JOIN project_member AS pm
             ON pm.project_id = p.id AND pm.workspace_id = p.workspace_id
            AND pm.user_id = wm.user_id
           WHERE p.workspace_id = ? AND p.id = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)""",
        (user_id, workspace_id, project_id),
    ).fetchone()


def get_effective_project_role(project_id, user_id):
    return get_db().execute(
        """SELECT CASE WHEN wm.role = 'owner' THEN 'admin' ELSE pm.role END AS role
           FROM project AS p
           JOIN workspace_member AS wm
             ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           LEFT JOIN project_member AS pm
             ON pm.project_id = p.id AND pm.workspace_id = p.workspace_id
            AND pm.user_id = wm.user_id
           WHERE p.id = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)""",
        (user_id, project_id),
    ).fetchone()


def get_project_workspace_id(project_id):
    row = get_db().execute(
        "SELECT workspace_id FROM project WHERE id = ?", (project_id,)
    ).fetchone()
    return row["workspace_id"] if row is not None else None


def get_projects_for_user(workspace_id, user_id):
    return get_db().execute(
        """SELECT p.id, p.workspace_id, p.name, p.description,
                  p.created_by, p.updated_by, p.created_at, p.updated_at,
                  CASE WHEN wm.role = 'owner' THEN 'admin' ELSE pm.role END AS role
           FROM project AS p
           JOIN workspace_member AS wm
             ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           LEFT JOIN project_member AS pm
             ON pm.project_id = p.id AND pm.workspace_id = p.workspace_id
            AND pm.user_id = wm.user_id
           WHERE p.workspace_id = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)
           ORDER BY p.created_at DESC, p.id DESC""",
        (user_id, workspace_id),
    ).fetchall()


def update_project(project_id, name, description, updated_by):
    get_db().execute(
        """UPDATE project
           SET name = ?, description = ?, updated_by = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (name, description, updated_by, project_id),
    )


def delete_project(workspace_id, project_id):
    get_db().execute(
        "DELETE FROM project WHERE workspace_id = ? AND id = ?",
        (workspace_id, project_id),
    )


def get_workspace_member_role(workspace_id, user_id):
    row = get_db().execute(
        """SELECT role FROM workspace_member
           WHERE workspace_id = ? AND user_id = ?""",
        (workspace_id, user_id),
    ).fetchone()
    return row["role"] if row is not None else None


def get_project_member(project_id, user_id):
    return get_db().execute(
        """SELECT pm.project_id, pm.workspace_id, pm.user_id,
                  u.username, pm.role, pm.joined_at
           FROM project_member AS pm
           JOIN user AS u ON u.id = pm.user_id
           WHERE pm.project_id = ? AND pm.user_id = ?""",
        (project_id, user_id),
    ).fetchone()


def get_project_member_role(project_id, user_id):
    row = get_db().execute(
        """SELECT role FROM project_member
           WHERE project_id = ? AND user_id = ?""",
        (project_id, user_id),
    ).fetchone()
    return row["role"] if row is not None else None


def get_project_members(project_id):
    return get_db().execute(
        """SELECT u.id, u.username, pm.role, pm.joined_at
           FROM project_member AS pm
           JOIN user AS u ON u.id = pm.user_id
           WHERE pm.project_id = ?
           ORDER BY pm.joined_at ASC, u.id ASC""",
        (project_id,),
    ).fetchall()


def insert_project_member(project_id, workspace_id, user_id, role):
    get_db().execute(
        """INSERT INTO project_member (project_id, workspace_id, user_id, role)
           VALUES (?, ?, ?, ?)""",
        (project_id, workspace_id, user_id, role),
    )


def update_project_member_role(project_id, user_id, role):
    get_db().execute(
        """UPDATE project_member SET role = ?
           WHERE project_id = ? AND user_id = ?""",
        (role, project_id, user_id),
    )


def delete_project_member(project_id, user_id):
    get_db().execute(
        "DELETE FROM project_member WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    )


def member_has_assigned_tasks(project_id, user_id):
    return get_db().execute(
        """SELECT 1 FROM task
           WHERE project_id = ? AND assignee_id = ?
           LIMIT 1""",
        (project_id, user_id),
    ).fetchone() is not None
