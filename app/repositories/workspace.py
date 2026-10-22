from app.core.db import get_db


def insert_workspace(name, description, created_by):
    cursor = get_db().execute(
        """INSERT INTO workspace (name, description, created_by)
           VALUES (?, ?, ?)""",
        (name, description, created_by),
    )
    return cursor.lastrowid


def insert_workspace_member(workspace_id, user_id, role):
    get_db().execute(
        """INSERT INTO workspace_member (workspace_id, user_id, role)
           VALUES (?, ?, ?)""",
        (workspace_id, user_id, role),
    )


def delete_workspace(workspace_id):
    get_db().execute(
        "DELETE FROM workspace WHERE id = ?",
        (workspace_id,),
    )


def get_workspace_for_member(workspace_id, user_id):
    return get_db().execute(
        """SELECT w.id, w.name, w.description, w.created_by, w.created_at,
                  w.updated_at, wm.role
           FROM workspace AS w
           JOIN workspace_member AS wm ON wm.workspace_id = w.id
           WHERE w.id = ? AND wm.user_id = ?""",
        (workspace_id, user_id),
    ).fetchone()


def get_workspace_member_role(workspace_id, user_id):
    row = get_db().execute(
        """SELECT role FROM workspace_member
           WHERE workspace_id = ? AND user_id = ?""",
        (workspace_id, user_id),
    ).fetchone()
    return row["role"] if row is not None else None


def get_workspace_members(workspace_id):
    return get_db().execute(
        """SELECT wm.user_id, u.username, u.display_name, u.email,
                  wm.role, wm.joined_at
           FROM workspace_member AS wm
           JOIN user AS u ON u.id = wm.user_id
           WHERE wm.workspace_id = ?
           ORDER BY CASE wm.role
               WHEN 'owner' THEN 0 WHEN 'admin' THEN 1 ELSE 2 END,
               u.username COLLATE NOCASE, wm.user_id""",
        (workspace_id,),
    ).fetchall()


def get_workspace_member(workspace_id, user_id):
    return get_db().execute(
        """SELECT wm.user_id, u.username, u.display_name, u.email,
                  wm.role, wm.joined_at
           FROM workspace_member AS wm
           JOIN user AS u ON u.id = wm.user_id
           WHERE wm.workspace_id = ? AND wm.user_id = ?""",
        (workspace_id, user_id),
    ).fetchone()


def user_exists(user_id):
    return get_db().execute(
        "SELECT 1 FROM user WHERE id = ?", (user_id,)
    ).fetchone() is not None


def update_workspace(workspace_id, actor_id, values):
    assignments = ", ".join(f"{column} = ?" for column in values)
    parameters = [*values.values(), actor_id, workspace_id]
    get_db().execute(
        f"""UPDATE workspace
            SET {assignments}, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
        parameters,
    )


def update_workspace_member_role(workspace_id, user_id, role):
    get_db().execute(
        """UPDATE workspace_member SET role = ?
           WHERE workspace_id = ? AND user_id = ?""",
        (role, workspace_id, user_id),
    )


def delete_workspace_member(workspace_id, user_id):
    get_db().execute(
        "DELETE FROM workspace_member WHERE workspace_id = ? AND user_id = ?",
        (workspace_id, user_id),
    )


def count_workspace_admins(workspace_id):
    return get_db().execute(
        """SELECT COUNT(*) FROM workspace_member
           WHERE workspace_id = ? AND role = 'admin'""",
        (workspace_id,),
    ).fetchone()[0]


def get_member_projects(workspace_id, user_id):
    return get_db().execute(
        """SELECT p.id, p.name,
                  CASE WHEN wm.role = 'owner' THEN 'admin' ELSE pm.role END AS role
           FROM project AS p
           JOIN workspace_member AS wm
             ON wm.workspace_id = p.workspace_id AND wm.user_id = ?
           LEFT JOIN project_member AS pm
             ON pm.project_id = p.id AND pm.workspace_id = p.workspace_id
            AND pm.user_id = wm.user_id
           WHERE p.workspace_id = ?
             AND (wm.role = 'owner' OR pm.user_id IS NOT NULL)
           ORDER BY p.id""",
        (user_id, workspace_id),
    ).fetchall()


def get_member_tasks(workspace_id, user_id):
    return get_db().execute(
        """SELECT t.id, t.project_id, p.name AS project_name, t.title
           FROM task AS t
           JOIN project AS p ON p.id = t.project_id
           WHERE p.workspace_id = ? AND t.assignee_id = ?
           ORDER BY t.id""",
        (workspace_id, user_id),
    ).fetchall()


def unassign_member_tasks(workspace_id, user_id, actor_id):
    get_db().execute(
        """UPDATE task
           SET assignee_id = NULL, updated_by = ?, updated_at = CURRENT_TIMESTAMP
           WHERE assignee_id = ?
             AND project_id IN (
                 SELECT id FROM project WHERE workspace_id = ?
             )""",
        (actor_id, user_id, workspace_id),
    )


def get_workspaces_for_user(user_id):
    return get_db().execute(
        """SELECT w.id, w.name, w.description, w.created_by, w.created_at,
                  w.updated_at, wm.role
           FROM workspace AS w
           JOIN workspace_member AS wm ON wm.workspace_id = w.id
           WHERE wm.user_id = ?
           ORDER BY w.created_at DESC, w.id DESC""",
        (user_id,),
    ).fetchall()
