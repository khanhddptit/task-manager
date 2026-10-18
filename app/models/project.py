from app.db import get_db


def get_effective_project_role(project_id, user_id):
    return get_db().execute(
        """SELECT CASE WHEN wm.role = 'owner' THEN 'admin' ELSE pm.role END AS role
           FROM project AS p
           JOIN workspace_member AS wm
             ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           LEFT JOIN project_member AS pm
             ON pm.project_id = p.id AND pm.user_id = wm.user_id
           WHERE p.id = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)""",
        (user_id, project_id),
    ).fetchone()


def get_project_workspace_id(project_id):
    row = get_db().execute(
        "SELECT workspace_id FROM project WHERE id = ?", (project_id,)
    ).fetchone()
    return row["workspace_id"] if row is not None else None


def get_project_member_role(project_id, user_id):
    row = get_db().execute(
        """SELECT role FROM project_member
           WHERE project_id = ? AND user_id = ?""",
        (project_id, user_id),
    ).fetchone()
    return row["role"] if row is not None else None


def get_project_member(project_id, user_id):
    return get_db().execute(
        """SELECT pm.project_id, pm.user_id, u.username, pm.role, pm.joined_at
           FROM project_member AS pm
           JOIN user AS u ON u.id = pm.user_id
           WHERE pm.project_id = ? AND pm.user_id = ?""",
        (project_id, user_id),
    ).fetchone()


def update_project_member_role(project_id, user_id, role):
    get_db().execute(
        """UPDATE project_member SET role = ?
           WHERE project_id = ? AND user_id = ?""",
        (role, project_id, user_id),
    )


def insert_project_member(project_id, workspace_id, user_id, role):
    get_db().execute(
        """INSERT INTO project_member
               (project_id, workspace_id, user_id, role)
           VALUES (?, ?, ?, ?)""",
        (project_id, workspace_id, user_id, role),
    )
